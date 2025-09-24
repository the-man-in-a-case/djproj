import yaml
from kubernetes import client, config, utils
from django.conf import settings


def _load_kube():
    if settings.K8S_INCLUSTER: 
        config.load_incluster_config()
    else:
        try:
            if settings.K8S_CONTEXT: 
                config.load_kube_config(context=settings.K8S_CONTEXT)
            else: 
                config.load_kube_config()
        except Exception: 
            pass


def apply_yaml(multidoc_yaml: str, namespace: str=None):
    _load_kube()
    k8s_client = client.ApiClient()
    
    # Instead of using StringIO, we'll parse the YAML and apply each document individually
    yaml_docs = yaml.safe_load_all(multidoc_yaml)
    created_objects = []
    
    for doc in yaml_docs:
        if doc is None:  # Skip empty documents
            continue
            
        try:
            # Create the object using the appropriate API based on kind
            kind = doc.get('kind')
            api_version = doc.get('apiVersion')
            metadata = doc.get('metadata', {})
            
            # Set namespace if not specified in the document
            if namespace and 'namespace' not in metadata:
                metadata['namespace'] = namespace
            
            # Apply the object using the dynamic client
            # This is a more flexible approach than create_from_yaml
            created = utils.create_from_dict(k8s_client, doc)
            created_objects.append(created)
        except Exception as e:
            # Log the error but continue with other documents
            print(f"Error applying YAML document: {str(e)}")
            continue
    
    return [getattr(obj, "metadata", None).name if hasattr(obj, "metadata") else str(obj) for obj in created_objects]
