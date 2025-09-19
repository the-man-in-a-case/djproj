import json, time, threading
from django.core.management.base import BaseCommand
from django.conf import settings
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from projects.models import Project, WorkerRun

def _watch(pid: str):
    import redis
    try:
        # 改进Redis连接逻辑，确保连接稳定
        r = redis.from_url(settings.WORKER_RESULT_REDIS, decode_responses=True)
        r.ping()
        print(f"✅ 成功连接到Redis并监控项目 {pid} 的频道: project:{pid}:worker_events")
        
        # 重新创建pubsub对象，确保每次都有新的连接
        ps = r.pubsub(ignore_subscribe_messages=True)
        ps.subscribe(f"project:{pid}:worker_events")
        
        # 添加连接状态检查
        print(f"✅ 已订阅频道: project:{pid}:worker_events")
        
        while True:
            # 使用listen()方法代替get_message()，更稳定地接收消息
            for message in ps.listen():
                if message and message.get('type') == 'message':
                    # 打印所有收到的消息，与print_redis_messages.py格式保持一致
                    print(f"\n📨 收到项目 {pid} 的新消息:")
                    print(f"  频道: {message['channel']}")
                    try:
                        data = json.loads(message['data'])
                        print(f"  数据: {json.dumps(data, indent=2, ensure_ascii=False)}")
                    except Exception as e:
                        data = {'raw': message['data']}
                        print(f"  数据解析失败: {e}, 原始数据: {message['data']}")
                    print("=" * 60)
                    
                    # 处理WorkerRun状态更新
                    if data.get('run_id'):
                        try:
                            run = WorkerRun.objects.get(id=data['run_id'])
                            old_status = run.status
                            run.status = data.get('status', run.status)
                            run.message = data.get('message')
                            run.save(update_fields=['status', 'message', 'updated_at'])
                            print(f"🔄 更新WorkerRun {data['run_id']} 状态: {old_status} -> {run.status}")
                        except WorkerRun.DoesNotExist:
                            print(f"❌ WorkerRun {data['run_id']} 不存在")
                    # 检查项目状态
                    _check(pid, r)
            
            # 如果listen()退出循环，短暂休眠后重新开始
            time.sleep(0.1)
            
    except Exception as e:
        print(f"❌ 监控项目 {pid} 时发生错误: {e}")
        # 发生异常时重新连接
        time.sleep(1)  # 避免频繁重连
        _watch(pid)  # 递归调用重新开始监控

def _check(pid, r):
    try:
        completed = int(r.get(f"project:{pid}:completed_count") or 0)
        errors = int(r.get(f"project:{pid}:errors_count") or 0)
        total = int(r.get(f"project:{pid}:targets_count") or 0)
        print(f"📊 检查项目 {pid}: 已完成: {completed}, 错误: {errors}, 总数: {total}")
        
        if total > 0 and (completed == total or errors > 0):
            try:
                p = Project.objects.get(id=pid)
                old_status = p.status
                p.status = "SUCCEEDED" if errors == 0 else "FAILED"
                p.save(update_fields=['status', 'updated_at'])
                print(f"🏁 更新项目 {pid} 状态: {old_status} -> {p.status}")
            except Project.DoesNotExist:
                print(f"❌ 项目 {pid} 不存在")
                return
            
            layer = get_channel_layer()
            event_data = {
                'type': 'notify', 
                'event': 'done', 
                'status': 'ok' if errors == 0 else 'error', 
                'completed': completed, 
                'errors': errors, 
                'total': total
            }
            print(f"📡 发送WebSocket事件: {event_data}")
            async_to_sync(layer.group_send)(f"project-{pid}", event_data)
    except Exception as e:
        print(f"❌ 检查项目 {pid} 状态时发生错误: {e}")

class Command(BaseCommand):
    help = "Monitor Redis pub/sub for worker events."
    
    def add_arguments(self, parser):
        parser.add_argument('--pid', type=str, help='指定要监控的项目ID，即使其状态为SUCCEEDED或FAILED')
        parser.add_argument('--debug', action='store_true', help='启用调试模式，监控测试频道')
        parser.add_argument('--forever', action='store_true', help='持续运行，不自动退出')
    
    def handle(self, *args, **kwargs):
        self.pid = kwargs.get('pid')
        self.debug = kwargs.get('debug', False)
        self.forever = kwargs.get('forever', False)
        
        print("🚀 启动监控worker命令")
        # 添加Redis连接测试
        import redis
        try:
            r = redis.from_url(settings.WORKER_RESULT_REDIS, decode_responses=True)
            r.ping()
            print(f"✅ 成功连接到Redis: {settings.WORKER_RESULT_REDIS}")
        except Exception as e:
            print(f"❌ Redis连接失败: {e}")
        
        monitored_projects = set()  # 跟踪已监控的项目，避免重复创建线程
        
        try:
            while True:
                pids = list(Project.objects.exclude(status__in=['SUCCEEDED', 'FAILED']).values_list('id', flat=True))
                print(f"📋 当前活跃项目数量: {len(pids)}, 项目ID: {pids}")
                
                # 添加手动指定项目ID监控的功能
                if self.pid:
                    print(f"🎯 手动监控项目ID: {self.pid}")
                    if self.pid not in pids:
                        pids.append(self.pid)
                
                # 即使没有活跃项目，也添加一个测试频道的订阅，用于调试
                if not pids and self.debug:
                    print("🔧 进入调试模式，监控测试频道")
                    pids = ['test-project']
                elif not pids:
                    self.stdout.write(self.style.WARNING("No active projects."))
                
                # 只创建新的项目的监控线程
                new_pids = [pid for pid in pids if pid not in monitored_projects]
                
                if new_pids:
                    print(f"✨ 发现新项目，创建监控线程: {new_pids}")
                    
                    for pid in new_pids:
                        try:
                            # 创建并启动监控线程
                            thread = threading.Thread(target=_watch, args=(str(pid),), daemon=True, name=f"Monitor-{pid}")
                            thread.start()
                            print(f"✅ 线程启动: {thread.name}")
                            monitored_projects.add(pid)
                        except Exception as e:
                            print(f"❌ 创建监控线程失败 (项目ID: {pid}): {e}")
                    
                    self.stdout.write(self.style.SUCCESS(f"✅ 已成功监控 {len(monitored_projects)} 个项目"))
                
                # 清理已完成的项目（从数据库中删除或状态已变更为SUCCEEDED/FAILED的项目）
                if monitored_projects:
                    active_pids = set(pids)
                    if self.pid:
                        active_pids.add(self.pid)
                    
                    completed_pids = monitored_projects - active_pids
                    if completed_pids:
                        print(f"🧹 清理已完成的项目监控: {completed_pids}")
                        monitored_projects -= completed_pids
                
                # 如果不是持续运行模式且没有监控的项目，则退出
                if not self.forever and not monitored_projects and not self.debug:
                    self.stdout.write(self.style.WARNING("No projects to monitor, exiting."))
                    break
                
                # 等待一段时间后再次检查
                wait_time = 10 if self.forever else 5
                print(f"⏱️ 等待 {wait_time} 秒后再次检查新项目...")
                time.sleep(wait_time)
        except KeyboardInterrupt:
            print("🛑 接收到中断信号")
            self.stdout.write("Exiting.")
        except Exception as e:
            print(f"❌ 监控命令执行出错: {e}")
            import traceback
            traceback.print_exc()

