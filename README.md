# djproj (Django+Channels+Celery/KEDA)
See k8s.yaml for cluster manifests; build images:
docker build -t djproj-web -f Dockerfile.web .
docker build -t djproj-worker -f Dockerfile.worker .
