import os
import sys
sys.path.insert(1, os.path.join(sys.path[0], '../../helpers'))
from helpers import helm_template
import yaml

project = 'filebeat'
name = 'RELEASE-NAME-' + project


def test_defaults():
    config = '''
    '''

    r = helm_template(config)

    assert name in r['daemonset']

    c = r['daemonset'][name]['spec']['template']['spec']['containers'][0]
    assert c['name'] == project
    assert c['image'].startswith('docker.elastic.co/beats/' + project + ':')
    assert c['ports'][0]['containerPort'] == 5066 # internal filebeat monitoring REST API

    assert c['env'][0]['name'] == 'POD_NAMESPACE'
    assert c['env'][0]['valueFrom']['fieldRef']['fieldPath'] == 'metadata.namespace'

    assert c['livenessProbe']['httpGet']['port'] == 'monitor'

    # Empty customizable defaults
    assert 'imagePullSecrets' not in r['daemonset'][name]['spec']['template']['spec']
    assert 'tolerations' not in r['daemonset'][name]['spec']['template']['spec']

    assert r['daemonset'][name]['spec']['updateStrategy']['type'] == 'RollingUpdate'


def test_adding_envs():
    config = '''
extraEnvs:
- name: LOG_LEVEL
  value: DEBUG
'''
    r = helm_template(config)
    envs = r['daemonset'][name]['spec']['template']['spec']['containers'][0]['env']
    assert {'name': 'LOG_LEVEL', 'value': 'DEBUG'} in envs


def test_adding_image_pull_secrets():
    config = '''
imagePullSecrets:
  - name: test-registry
'''
    r = helm_template(config)
    assert r['daemonset'][name]['spec']['template']['spec']['imagePullSecrets'][0]['name'] == 'test-registry'


def test_adding_tolerations():
    config = '''
tolerations:
- key: "key1"
  operator: "Equal"
  value: "value1"
  effect: "NoExecute"
  tolerationSeconds: 3600
'''
    r = helm_template(config)
    assert r['daemonset'][name]['spec']['template']['spec']['tolerations'][0]['key'] == 'key1'


def test_override_the_default_update_strategy():
    config = '''
updateStrategy: OnDelete
'''

    r = helm_template(config)
    assert r['daemonset'][name]['spec']['updateStrategy']['type'] == 'OnDelete'

def test_setting_a_custom_service_account():
    config = '''
serviceAccount: notdefault
'''
    r = helm_template(config)
    assert r['daemonset'][name]['spec']['template']['spec']['serviceAccountName'] == 'notdefault'

def test_self_managing_rbac_resources():
    config = '''
managedServiceAccount: false
'''
    r = helm_template(config)
    assert 'serviceaccount' not in r
    assert 'clusterrole' not in r
    assert 'clusterrolebinding' not in r

def test_setting_pod_security_context():
    config = '''
podSecurityContext:
  runAsUser: 1001
  fsGroup: 1002
  privileged: false
'''
    r = helm_template(config)
    c = r['daemonset'][name]['spec']['template']['spec']['containers'][0]
    assert c['securityContext']['runAsUser'] == 1001
    assert c['securityContext']['fsGroup'] == 1002
    assert c['securityContext']['privileged'] == False

def test_adding_in_filebeat_config():
    config = '''
filebeatConfig:
  filebeat.yml: |
    key:
      nestedkey: value
    dot.notation: test

  other-config.yml: |
    hello = world
'''
    r = helm_template(config)
    c = r['configmap'][project + '-config']['data']

    assert 'filebeat.yml' in c
    assert 'other-config.yml' in c

    assert 'nestedkey: value' in c['filebeat.yml']
    assert 'dot.notation: test' in c['filebeat.yml']

    assert 'hello = world' in c['other-config.yml']

    d = r['daemonset'][name]['spec']['template']['spec']

    assert {'configMap': {'name': project + '-config', 'defaultMode': 0600}, 'name': project + '-config'} in d['volumes']
    assert {'mountPath': '/usr/share/filebeat/filebeat.yml', 'name': project + '-config', 'subPath': 'filebeat.yml', 'readOnly': True} in d['containers'][0]['volumeMounts']
    assert {'mountPath': '/usr/share/filebeat/other-config.yml', 'name': project + '-config', 'subPath': 'other-config.yml', 'readOnly': True} in d['containers'][0]['volumeMounts']

    assert 'configChecksum' in r['daemonset'][name]['spec']['template']['metadata']['annotations']
