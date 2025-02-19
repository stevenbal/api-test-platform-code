import json
import yaml
import uuid
import os

from .kubernetes import *
from ..utils.commands import run_command, safeget


class K8S():

    def __init__(self, cluster='test-sessions', app_name=None):
        self.initialized = False
        self.cluster = cluster
        self.db_deployed = False
        self.db_to_deploy = False
        self.app_name = app_name
        self.containers = []
        self.script_folder = os.path.dirname(__file__)
        self.garbage = []
        self.deployment = None
        self.pod_name = None

    def __del__(self):
        for gfile in self.garbage:
            os.remove(gfile)

    def initialize(self):
        if self.initialized:
            return
        set_zone = [
            'gcloud',
            'config',
            'set',
            'compute/zone',
            'europe-west4-a'
        ]
        set_project = [
            'gcloud',
            'config',
            'set',
            'core/project',
            'vng-test-platform'
        ]
        create_cluster = [
            'gcloud',
            'container',
            'clusters',
            'create',
            self.cluster,
            '--num-nodes=1',
        ]
        get_credentials = [
            'gcloud',
            'container',
            'clusters',
            'get-credentials',
            self.cluster,
        ]
        run_command(set_zone)
        run_command(set_project)
        # Create a general cluster (will error if it already exists)
        run_command(create_cluster)
        # Get the credentials to use kubectl for the correct cluster
        run_command(get_credentials)

        self.initialized = True

    def fetch_resource(self, resource):
        fetch = [
            'kubectl',
            'get',
            resource,
            '--output=json'
        ]
        res = run_command(fetch).decode('utf-8')
        return json.loads(res)

    def delete(self):
        clean_up = [
            'kubectl',
            'delete',
            'deployment'
        ]
        deployments = self.fetch_resource('deployments')
        for item in deployments['items']:
            if safeget(item, 'metadata', 'name'):
                name = item['metadata']['name']
                if self.app_name in name:
                    # Delete the workload
                    run_command([*clean_up, name])

        # TODO: remove unused resources, remember that Kubernetes has a Garbage Collector integrated
        # svc still used

    def get_pod_log(self, c_name):
        if not self.pod_name:
            self.make_aware()
        log_command = [
            'kubectl',
            'logs',
            self.pod_name,
            '-c',
            c_name,
        ]
        try:
            res = run_command(log_command).decode('utf-8')
            return res
        except:
            raise Exception('Application {} not found in the deployed cluster'.format(self.app_name))

    def get_pod_status(self):
        status_command = [
            'kubectl',
            'get',
            'pods',
            '--output=json'
        ]
        res1 = run_command(status_command).decode('utf-8')
        pods = json.loads(res1)
        items = pods.get('items')
        for item in items:
            metadata = item.get('metadata')
            if metadata and metadata.get('name').startswith(self.app_name):
                return item
        raise Exception('Application {} not found in the deployed cluster'.format(self.app_name))

    def get_pod_status_deployment(self):
        status_command = [
            'kubectl',
            'get',
            'pods',
            '-o',
            'wide',
            '--output=json'
        ]
        res1 = run_command(status_command).decode('utf-8')
        pods = json.loads(res1)
        items = pods.get('items')
        for item in items:
            metadata = item.get('metadata')
            if metadata and metadata.get('name').startswith(self.app_name):
                status = item.get('status').get('containerStatuses')[0]
                if item.get('status').get('phase') == 'Pending':
                    return False, status.get('state').get('waiting').get('message')
                elif item.get('status').get('phase') == 'Running':
                    return True, None
        raise Exception('Application {} not found in the deployed cluster'.format(self.app_name))

    def service_status(self):
        status_command = [
            'kubectl',
            'get',
            'service',
            '--output=json'
        ]
        res1 = run_command(status_command).decode('utf-8')
        services = json.loads(res1)
        items = services.get('items')
        for item in items:
            metadata = item.get('metadata')
            if metadata and metadata.get('name').startswith(self.app_name):
                ip_list = item.get('status').get('loadBalancer').get('ingress')
                if ip_list:
                    return ip_list[0].get('ip')
                return None
        raise Exception('Application {} not found in the deployed cluster'.format(self.app_name))

    def make_aware(self):
        status = self.get_pod_status()
        self.pod_name = status['metadata']['name']
        self.deployment = status['metadata']['ownerReferences'][0]['name']

    def exec(self, commands):
        self.make_aware()
        exec_command = [
            'kubectl',
            'exec',
            self.pod_name,
            '--',
            *commands
        ]
        return run_command(exec_command).decode('utf-8')

    def copy_to(self, source, dest):
        self.make_aware()
        copy_command = [
            'kubectl',
            'cp',
            source,
            '{}:{}'.format(self.pod_name, dest)
        ]
        return run_command(copy_command).decode('utf-8')
