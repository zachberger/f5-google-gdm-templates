# Copyright 2019 F5 Networks All rights reserved.
#
# Version 3.4.0

""" Creates Deployment """
COMPUTE_URL_BASE = 'https://www.googleapis.com/compute/v1/'
def FirewallRuleApp(context):
# Build Application firewall rule
    ports = str(context.properties['applicationPort']).split()
    source_list = str(context.properties['restrictedSrcAddressApp']).split()
    firewallRuleApp = {
        'name': 'appfw-' + context.env['deployment'],
        'type': 'compute.v1.firewall',
        'properties': {
            'network': ''.join([COMPUTE_URL_BASE, 'projects/',
                                context.env['project'], '/global/networks/',
                                context.properties['mgmtNetwork']]),
            'sourceRanges': source_list,
            'targetTags': ['appfw-'+ context.env['deployment']],
            'allowed': [{
                "IPProtocol": "TCP",
                "ports": ports,
                },
            ]
        }
    }
    return firewallRuleApp

def FirewallRuleMgmt(context):
    # Build Management firewall rule
    source_list = str(context.properties['restrictedSrcAddress']).split()
    firewallRuleMgmt = {
        'name': 'mgmtfw-' + context.env['deployment'],
        'type': 'compute.v1.firewall',
        'properties': {
            'network': ''.join([COMPUTE_URL_BASE, 'projects/',
                                context.env['project'], '/global/networks/',
                                context.properties['mgmtNetwork']]),
            'sourceRanges': source_list,
            'targetTags': ['mgmtfw-'+ context.env['deployment']],
            'allowed': [{
                "IPProtocol": "TCP",
                "ports": [str(context.properties['mgmtGuiPort']),'22'],
                },
            ]
        }
    }
    return firewallRuleMgmt
def Instance(context):
    # declare specific instance properties ahead of time as they may change
    network_interfaces = [
            {
                'network': ''.join([COMPUTE_URL_BASE, 'projects/',
                                    context.env['project'], '/global/networks/',
                                    context.properties['mgmtNetwork']]),
                'subnetwork': ''.join([COMPUTE_URL_BASE, 'projects/',
                                    context.env['project'], '/regions/',
                                    context.properties['region'], '/subnetworks/',
                                    context.properties['mgmtSubnet']]),
                'accessConfigs': []

            }]

    # access config - conditional on provisionPublicIP parameter (boolean yes/no)
    if str(context.properties['provisionPublicIP']).lower() in ['yes', 'true']:
        network_interfaces[0]['accessConfigs'] = [{
            'name': 'Management NAT',
            'type': 'ONE_TO_ONE_NAT'
        }]
      

    # If not 'DYNAMIC'|'' assume a static address is needed
    mgmtSubnetAddress = context.properties['mgmtSubnetAddress'].upper()
    if mgmtSubnetAddress != "DYNAMIC" and mgmtSubnetAddress != "":
        network_interfaces[0]['networkIP'] = mgmtSubnetAddress
    # Build instance template
    instance = {
        'name': 'bigip1-' + context.env['deployment'],
        'type': 'compute.v1.instance',
        'properties': {
            'canIpForward': True,
            'description': 'F5 BIG-IP configured with 1 interface(s).',
            'hostname': ''.join(['bigip1-', context.env['deployment'], '.c.', context.env['project'], '.internal']),
            'disks': [{
                'deviceName': 'boot',
                'type': 'PERSISTENT',
                'boot': True,
                'autoDelete': True,
                'initializeParams': {
                    'sourceImage': ''.join([COMPUTE_URL_BASE, 'projects/f5-7626-networks-public',
                                            '/global/images/',
                                            context.properties['imageName'],
                                            ])
                }
            }],
            'machineType': 
        ''.join([COMPUTE_URL_BASE, 'projects/',
        context.env['project'], '/zones/',
        context.properties['availabilityZone1'], '/machineTypes/',
        context.properties['instanceType']]),
            'networkInterfaces': network_interfaces,
            'tags': {
              'items': [
                  'mgmtfw-' + context.env['deployment'],
                  'appfw-' + context.env['deployment']
              ]
            },
            'zone': context.properties['availabilityZone1'],
            'metadata': Metadata(context)

        }
    }

    # add no-ip tag if provisionPublicIP = no
    if str(context.properties['provisionPublicIP']).lower() in ['no', 'false']:
        instance['properties']['tags']['items'].append('no-ip')
    return instance

def Metadata(context):

    ALLOWUSAGEANALYTICS = str(context.properties['allowUsageAnalytics']).lower()
    if ALLOWUSAGEANALYTICS == 'yes':
        CUSTHASH = 'CUSTOMERID=`curl -s "http://metadata.google.internal/computeMetadata/v1/project/numeric-project-id" -H "Metadata-Flavor: Google" |sha512sum|cut -d " " -f 1`;\nDEPLOYMENTID=`curl -s "http://metadata.google.internal/computeMetadata/v1/instance/id" -H "Metadata-Flavor: Google"|sha512sum|cut -d " " -f 1`;'
        SENDANALYTICS = ' --metrics "cloudName:google,region:' + context.properties['region'] + ',bigipVersion:' + context.properties['imageName'] + ',customerId:${CUSTOMERID},deploymentId:${DEPLOYMENTID},templateName:f5-existing-stack-byol-1nic-bigip.py,templateVersion:3.4.0,licenseType:byol"'
    else:
        CUSTHASH = 'echo "No analytics."'
        SENDANALYTICS = ''
    # Provisioning modules
    PROVISIONING_MODULES = ','.join(context.properties['bigIpModules'].split('-'))

    ntp_servers = str(context.properties['ntpServer']).split()
    ntp_list = ''
    for ntp_server in ntp_servers:
        ntp_list = ntp_list + ' --ntp ' + ntp_server

    timezone = ' --tz UTC'
    if context.properties['timezone']:
       timezone = " --tz {0}".format(str(context.properties['timezone']))

    metadata = {
                'items': [{
                    'key': 'startup-script',
                    'value': ('\n'.join(['#!/bin/bash',
                                    'if [ -f /config/startupFinished ]; then',
                                    '    exit',
                                    'fi',
                                    'if [ ! -f /config/cloud/gce/FIRST_BOOT_COMPLETE ]; then',
                                    'mkdir -p /config/cloud/gce',
                                    'cat <<\'EOF\' > /config/installCloudLibs.sh',
                                    '#!/bin/bash',
                                    'echo about to execute',
                                    'checks=0',
                                    'while [ $checks -lt 120 ]; do echo checking mcpd',
                                    '    tmsh -a show sys mcp-state field-fmt | grep -q running',
                                    '    if [ $? == 0 ]; then',
                                    '        echo mcpd ready',
                                    '        break',
                                    '    fi',
                                    '    echo mcpd not ready yet',
                                    '    let checks=checks+1',
                                    '    sleep 10',
                                    'done',
                                    'echo loading verifyHash script',
                                    'if ! tmsh load sys config merge file /config/verifyHash; then',
                                    '    echo cannot validate signature of /config/verifyHash',
                                    '    exit',
                                    'fi',
                                    'echo loaded verifyHash',
                                    'declare -a filesToVerify=(\"/config/cloud/f5-cloud-libs.tar.gz\" \"/config/cloud/f5-cloud-libs-gce.tar.gz\" \"/config/cloud/f5-appsvcs-3.5.1-5.noarch.rpm\" \"/config/cloud/f5.service_discovery.tmpl\")',
                                    'for fileToVerify in \"${filesToVerify[@]}\"',
                                    'do',
                                    '    echo verifying \"$fileToVerify\"',
                                    '    if ! tmsh run cli script verifyHash \"$fileToVerify\"; then',
                                    '        echo \"$fileToVerify\" is not valid',
                                    '        exit 1',
                                    '    fi',
                                    '    echo verified \"$fileToVerify\"',
                                    'done',
                                    'mkdir -p /config/cloud/gce/node_modules/@f5devcentral',
                                    'echo expanding f5-cloud-libs.tar.gz\n',
                                    'tar xvfz /config/cloud/f5-cloud-libs.tar.gz -C /config/cloud/gce/node_modules/@f5devcentral',
                                    'echo expanding f5-cloud-libs-gce.tar.gz',
                                    'tar xvfz /config/cloud/f5-cloud-libs-gce.tar.gz -C /config/cloud/gce/node_modules/@f5devcentral',
                                    'echo cloud libs install complete',
                                    'touch /config/cloud/cloudLibsReady',
                                    'EOF',
                                    'echo \'Y2xpIHNjcmlwdCAvQ29tbW9uL3ZlcmlmeUhhc2ggewpwcm9jIHNjcmlwdDo6cnVuIHt9IHsKICAgICAgICBpZiB7W2NhdGNoIHsKICAgICAgICAgICAgc2V0IGhhc2hlcyhmNS1jbG91ZC1saWJzLnRhci5neikgZmNjMDk1OTg0ZmNkM2FiMWYzYmRlNzk0MDgyMjQwODZlYzM0OTgxZGFkYTljYzI0MTA3YzJlNTM5ZTIyOTc4NTZkZjk4N2RmYzRjNDc5NWMxNzFjNWVlYzhmMTIxZDE0NDI5YjNlNGI3MmM1YWQzMmZkZTk0ZTJjNmJmZGEwZGIKICAgICAgICAgICAgc2V0IGhhc2hlcyhmNS1jbG91ZC1saWJzLWF3cy50YXIuZ3opIDJmZjRlNjI2OWNlNzQ4NTBmYzM3OTQwNDVkMGEzOTRlY2QwYjQ3MmJhOWVmYTE2YjM0Nzg2YjM4ZDA3MDg4YjNhNDkzMzliNDE3MDg5NzNjNGJmZmU1NWE1Mzk0NzFjMmY5ZWM2MGEwMDlkZGQwODc5MTJjMWZjYTcyMmI0OGVmCiAgICAgICAgICAgIHNldCBoYXNoZXMoZjUtY2xvdWQtbGlicy1henVyZS50YXIuZ3opIDZkYjI4NzhhMmMxMGQ5ODU1MGVkZWQ2YjY2ZjA0NzQ1MTZjMTk1MmQzNjA1MjE3MTY0ZTNiNTI2MWM3NzE0MTkyMDFkOTRjN2NkYjA3NzQ0YzlkNWRiODk0MzM0ZjkzMzgwOTYzMjE3YjY3MGQ4N2QzMTUxYmZjZGIzMDFjMjk1CiAgICAgICAgICAgIHNldCBoYXNoZXMoZjUtY2xvdWQtbGlicy1nY2UudGFyLmd6KSBhNWNmYWVkMWZlMzNkYTY3N2IzZjEwZGMxYTdjYTgyZjU3MzlmZjI0ZTQ1ZTkxYjNhOGY3YjA2ZDZiMmUyODBlNWYxZWFmNWZlMmQzMzAwOWIyY2M2N2MxMGYyZDkwNmFhYjI2Zjk0MmQ1OTFiNjhmYThhN2ZkZGZkNTRhMGVmZQogICAgICAgICAgICBzZXQgaGFzaGVzKGY1LWNsb3VkLWxpYnMtb3BlbnN0YWNrLnRhci5neikgNWM4M2ZlNmE5M2E2ZmNlYjVhMmU4NDM3YjVlZDhjYzlmYWY0YzE2MjFiZmM5ZTZhMDc3OWY2YzIxMzdiNDVlYWI4YWUwZTdlZDc0NWM4Y2Y4MjFiOTM3MTI0NWNhMjk3NDljYTBiN2U1NjYzOTQ5ZDc3NDk2Yjg3MjhmNGIwZjkKICAgICAgICAgICAgc2V0IGhhc2hlcyhmNS1jbG91ZC1saWJzLWNvbnN1bC50YXIuZ3opIGEzMmFhYjM5NzA3M2RmOTJjYmJiYTUwNjdlNTgyM2U5YjVmYWZjYTg2MmEyNThiNjBiNmI0MGFhMDk3NWMzOTg5ZDFlMTEwZjcwNjE3N2IyZmZiZTRkZGU2NTMwNWEyNjBhNTg1NjU5NGNlN2FkNGVmMGM0N2I2OTRhZTRhNTEzCiAgICAgICAgICAgIHNldCBoYXNoZXMoYXNtLXBvbGljeS1saW51eC50YXIuZ3opIDYzYjVjMmE1MWNhMDljNDNiZDg5YWYzNzczYmJhYjg3YzcxYTZlN2Y2YWQ5NDEwYjIyOWI0ZTBhMWM0ODNkNDZmMWE5ZmZmMzlkOTk0NDA0MWIwMmVlOTI2MDcyNDAyNzQxNGRlNTkyZTk5ZjRjMjQ3NTQxNTMyM2UxOGE3MmUwCiAgICAgICAgICAgIHNldCBoYXNoZXMoZjUuaHR0cC52MS4yLjByYzQudG1wbCkgNDdjMTlhODNlYmZjN2JkMWU5ZTljMzVmMzQyNDk0NWVmODY5NGFhNDM3ZWVkZDE3YjZhMzg3Nzg4ZDRkYjEzOTZmZWZlNDQ1MTk5YjQ5NzA2NGQ3Njk2N2IwZDUwMjM4MTU0MTkwY2EwYmQ3Mzk0MTI5OGZjMjU3ZGY0ZGMwMzQKICAgICAgICAgICAgc2V0IGhhc2hlcyhmNS5odHRwLnYxLjIuMHJjNi50bXBsKSA4MTFiMTRiZmZhYWI1ZWQwMzY1ZjAxMDZiYjVjZTVlNGVjMjIzODU2NTVlYTNhYzA0ZGUyYTM5YmQ5OTQ0ZjUxZTM3MTQ2MTlkYWU3Y2E0MzY2MmM5NTZiNTIxMjIyODg1OGYwNTkyNjcyYTI1NzlkNGE4Nzc2OTE4NmUyY2JmZQogICAgICAgICAgICBzZXQgaGFzaGVzKGY1Lmh0dHAudjEuMi4wcmM3LnRtcGwpIDIxZjQxMzM0MmU5YTdhMjgxYTBmMGUxMzAxZTc0NWFhODZhZjIxYTY5N2QyZTZmZGMyMWRkMjc5NzM0OTM2NjMxZTkyZjM0YmYxYzJkMjUwNGMyMDFmNTZjY2Q3NWM1YzEzYmFhMmZlNzY1MzIxMzY4OWVjM2M5ZTI3ZGZmNzdkCiAgICAgICAgICAgIHNldCBoYXNoZXMoZjUuYXdzX2FkdmFuY2VkX2hhLnYxLjMuMHJjMS50bXBsKSA5ZTU1MTQ5YzAxMGMxZDM5NWFiZGFlM2MzZDJjYjgzZWMxM2QzMWVkMzk0MjQ2OTVlODg2ODBjZjNlZDVhMDEzZDYyNmIzMjY3MTFkM2Q0MGVmMmRmNDZiNzJkNDE0YjRjYjhlNGY0NDVlYTA3MzhkY2JkMjVjNGM4NDNhYzM5ZAogICAgICAgICAgICBzZXQgaGFzaGVzKGY1LmF3c19hZHZhbmNlZF9oYS52MS40LjByYzEudG1wbCkgZGUwNjg0NTUyNTc0MTJhOTQ5ZjFlYWRjY2FlZTg1MDYzNDdlMDRmZDY5YmZiNjQ1MDAxYjc2ZjIwMDEyNzY2OGU0YTA2YmUyYmJiOTRlMTBmZWZjMjE1Y2ZjMzY2NWIwNzk0NWU2ZDczM2NiZTFhNGZhMWI4OGU4ODE1OTAzOTYKICAgICAgICAgICAgc2V0IGhhc2hlcyhmNS5hd3NfYWR2YW5jZWRfaGEudjEuNC4wcmMyLnRtcGwpIDZhYjBiZmZjNDI2ZGY3ZDMxOTEzZjlhNDc0YjFhMDc4NjA0MzVlMzY2YjA3ZDc3YjMyMDY0YWNmYjI5NTJjMWYyMDdiZWFlZDc3MDEzYTE1ZTQ0ZDgwZDc0ZjMyNTNlN2NmOWZiYmUxMmE5MGVjNzEyOGRlNmZhY2QwOTdkNjhmCiAgICAgICAgICAgIHNldCBoYXNoZXMoZjUuYXdzX2FkdmFuY2VkX2hhLnYxLjQuMHJjMy50bXBsKSAyZjIzMzliNGJjM2EyM2M5Y2ZkNDJhYWUyYTZkZTM5YmEwNjU4MzY2ZjI1OTg1ZGUyZWE1MzQxMGE3NDVmMGYxOGVlZGM0OTFiMjBmNGE4ZGJhOGRiNDg5NzAwOTZlMmVmZGNhN2I4ZWZmZmExYTgzYTc4ZTVhYWRmMjE4YjEzNAogICAgICAgICAgICBzZXQgaGFzaGVzKGY1LmF3c19hZHZhbmNlZF9oYS52MS40LjByYzQudG1wbCkgMjQxOGFjOGIxZjE4ODRjNWMwOTZjYmFjNmE5NGQ0MDU5YWFhZjA1OTI3YTZhNDUwOGZkMWYyNWI4Y2M2MDc3NDk4ODM5ZmJkZGE4MTc2ZDJjZjJkMjc0YTI3ZTZhMWRhZTJhMWUzYTBhOTk5MWJjNjVmYzc0ZmMwZDAyY2U5NjMKICAgICAgICAgICAgc2V0IGhhc2hlcyhmNS5hd3NfYWR2YW5jZWRfaGEudjEuNC4wcmM1LnRtcGwpIDVlNTgyMTg3YWUxYTYzMjNlMDk1ZDQxZWRkZDQxMTUxZDZiZDM4ZWI4M2M2MzQ0MTBkNDUyN2EzZDBlMjQ2YThmYzYyNjg1YWIwODQ5ZGUyYWRlNjJiMDI3NWY1MTI2NGQyZGVhY2NiYzE2Yjc3MzQxN2Y4NDdhNGExZWE5YmM0CiAgICAgICAgICAgIHNldCBoYXNoZXMoYXNtLXBvbGljeS50YXIuZ3opIDJkMzllYzYwZDAwNmQwNWQ4YTE1NjdhMWQ4YWFlNzIyNDE5ZThiMDYyYWQ3N2Q2ZDlhMzE2NTI5NzFlNWU2N2JjNDA0M2Q4MTY3MWJhMmE4YjEyZGQyMjllYTQ2ZDIwNTE0NGY3NTM3NGVkNGNhZTU4Y2VmYThmOWFiNjUzM2U2CiAgICAgICAgICAgIHNldCBoYXNoZXMoZGVwbG95X3dhZi5zaCkgMWEzYTNjNjI3NGFiMDhhN2RjMmNiNzNhZWRjOGQyYjJhMjNjZDllMGViMDZhMmUxNTM0YjM2MzJmMjUwZjFkODk3MDU2ZjIxOWQ1YjM1ZDNlZWQxMjA3MDI2ZTg5OTg5Zjc1NDg0MGZkOTI5NjljNTE1YWU0ZDgyOTIxNGZiNzQKICAgICAgICAgICAgc2V0IGhhc2hlcyhmNS5wb2xpY3lfY3JlYXRvci50bXBsKSAwNjUzOWUwOGQxMTVlZmFmZTU1YWE1MDdlY2I0ZTQ0M2U4M2JkYjFmNTgyNWE5NTE0OTU0ZWY2Y2E1NmQyNDBlZDAwYzdiNWQ2N2JkOGY2N2I4MTVlZTlkZDQ2NDUxOTg0NzAxZDA1OGM4OWRhZTI0MzRjODk3MTVkMzc1YTYyMAogICAgICAgICAgICBzZXQgaGFzaGVzKGY1LnNlcnZpY2VfZGlzY292ZXJ5LnRtcGwpIDQ4MTFhOTUzNzJkMWRiZGJiNGY2MmY4YmNjNDhkNGJjOTE5ZmE0OTJjZGEwMTJjODFlM2EyZmU2M2Q3OTY2Y2MzNmJhODY3N2VkMDQ5YTgxNGE5MzA0NzMyMzRmMzAwZDNmOGJjZWQyYjBkYjYzMTc2ZDUyYWM5OTY0MGNlODFiCiAgICAgICAgICAgIHNldCBoYXNoZXMoZjUuY2xvdWRfbG9nZ2VyLnYxLjAuMC50bXBsKSA2NGEwZWQzYjVlMzJhMDM3YmE0ZTcxZDQ2MDM4NWZlOGI1ZTFhZWNjMjdkYzBlODUxNGI1MTE4NjM5NTJlNDE5YTg5ZjRhMmE0MzMyNmFiYjU0M2JiYTliYzM0Mzc2YWZhMTE0Y2VkYTk1MGQyYzNiZDA4ZGFiNzM1ZmY1YWQyMAogICAgICAgICAgICBzZXQgaGFzaGVzKGY1LWFwcHN2Y3MtMy41LjEtNS5ub2FyY2gucnBtKSBiYTcxYzZlMWM1MmQwYzcwNzdjZGIyNWE1ODcwOWI4ZmI3YzM3YjM0NDE4YTgzMzhiYmY2NzY2ODMzOTY3NmQyMDhjMWE0ZmVmNGU1NDcwYzE1MmFhYzg0MDIwYjRjY2I4MDc0Y2UzODdkZTI0YmUzMzk3MTEyNTZjMGZhNzhjOAogICAgICAgICAgICBzZXQgaGFzaGVzKGY1LWNsb3VkLWZhaWxvdmVyLTEuMS4wLTAubm9hcmNoLnJwbSkgMTVhNDQwYzI5OWY5ZTRhZjg2YTNkMGY1YjBkNzViMDA1NDM4NWI5NWU0N2MzZWYxMTZkMmUwYmZiMDA0MWEyNmRjYmY1NDkwMjhlMmEyNmQyYzcxOGVjNjE0NDZiZDY1N2JlMzhmYmJjZDlkYjc4MWVmZTU0MTRjMTc0YWM2OGMKCiAgICAgICAgICAgIHNldCBmaWxlX3BhdGggW2xpbmRleCAkdG1zaDo6YXJndiAxXQogICAgICAgICAgICBzZXQgZmlsZV9uYW1lIFtmaWxlIHRhaWwgJGZpbGVfcGF0aF0KCiAgICAgICAgICAgIGlmIHshW2luZm8gZXhpc3RzIGhhc2hlcygkZmlsZV9uYW1lKV19IHsKICAgICAgICAgICAgICAgIHRtc2g6OmxvZyBlcnIgIk5vIGhhc2ggZm91bmQgZm9yICRmaWxlX25hbWUiCiAgICAgICAgICAgICAgICBleGl0IDEKICAgICAgICAgICAgfQoKICAgICAgICAgICAgc2V0IGV4cGVjdGVkX2hhc2ggJGhhc2hlcygkZmlsZV9uYW1lKQogICAgICAgICAgICBzZXQgY29tcHV0ZWRfaGFzaCBbbGluZGV4IFtleGVjIC91c3IvYmluL29wZW5zc2wgZGdzdCAtciAtc2hhNTEyICRmaWxlX3BhdGhdIDBdCiAgICAgICAgICAgIGlmIHsgJGV4cGVjdGVkX2hhc2ggZXEgJGNvbXB1dGVkX2hhc2ggfSB7CiAgICAgICAgICAgICAgICBleGl0IDAKICAgICAgICAgICAgfQogICAgICAgICAgICB0bXNoOjpsb2cgZXJyICJIYXNoIGRvZXMgbm90IG1hdGNoIGZvciAkZmlsZV9wYXRoIgogICAgICAgICAgICBleGl0IDEKICAgICAgICB9XX0gewogICAgICAgICAgICB0bXNoOjpsb2cgZXJyIHtVbmV4cGVjdGVkIGVycm9yIGluIHZlcmlmeUhhc2h9CiAgICAgICAgICAgIGV4aXQgMQogICAgICAgIH0KICAgIH0KICAgIHNjcmlwdC1zaWduYXR1cmUgZk8xL2ZkRVNtZnNxTVR6OHRBTFJMa2tZcTN0N3NkNWlKTDcvbEVXVnRzSTBCd1ZSb1Urb0xacEdkczRjWW5zc1ZqM2I1aHBocFpKUGFZUERaYUlIWDZleURFLy9HS2FqZkVjdExSZDVxSDRYUURnd0RmMitqZ1REbjN5MDBSRk1ZdjB5TW9qeXBrTHhKT3BZRG5hVUZqTWhVNWN4a3pKeStqckswQnpWV2dEWk83TUYwTm9WL083NEQram01TmlJNmFCOStHZ0VtemJ6V3k2eHgzMFF6Z01uUW5qLzhjRlNKN0Nac2ZGZzRsZC9mQXE3a2oybm9qK1I3M1pUd1NhWXRJRHZyM254d3IzT3J1a21GNlptRFEvekxEb084bTgreXB4akFTWVNFNjBRbi9mU2JsQ1ZnaE5IdUZtWmVGOXJhWnQvZ2xMN3JNUUl5TmxHc1BBYUJRPT0KICAgIHNpZ25pbmcta2V5IC9Db21tb24vZjUtaXJ1bGUKfQ==\' | base64 -d > /config/verifyHash',
                                    'cat <<\'EOF\' > /config/waitThenRun.sh',
                                    '#!/bin/bash',
                                    'while true; do echo \"waiting for cloud libs install to complete\"',
                                    '    if [ -f /config/cloud/cloudLibsReady ]; then',
                                    '        echo "Running f5-cloud-libs Version:"',
                                    '        f5-rest-node /config/cloud/gce/node_modules/@f5devcentral/f5-cloud-libs/scripts/onboard.js --version',
                                    '        break',
                                    '    else',
                                    '        sleep 10',
                                    '    fi',
                                    'done',
                                    '\"$@\"',
                                    'EOF',
                                    'cat <<\'EOF\' > /config/cloud/gce/custom-config.sh',
                                    '#!/bin/bash',
                                    'PROGNAME=$(basename $0)',
                                    'function error_exit {',
                                    'echo \"${PROGNAME}: ${1:-\\\"Unknown Error\\\"}\" 1>&2',
                                    'exit 1',
                                    '}',
                                    'function wait_for_ready {',
                                    '   checks=0',
                                    '   ready_response=""',
                                    '   ready_response_declare=""',
                                    '   while [ $checks -lt 120 ] ; do',
                                    '      ready_response=$(curl -sku admin:$passwd -w "%{http_code}" -X GET  https://localhost:${mgmtGuiPort}/mgmt/shared/appsvcs/info -o /dev/null)',
                                    '      ready_response_declare=$(curl -sku admin:$passwd -w "%{http_code}" -X GET  https://localhost:${mgmtGuiPort}/mgmt/shared/appsvcs/declare -o /dev/null)',
                                    '      if [[ $ready_response == *200 && $ready_response_declare == *204 ]]; then',
                                    '          echo "AS3 is ready"',
                                    '          break',
                                    '      else',
                                    '         echo "AS3" is not ready: $checks, response: $ready_response $ready_response_declare',
                                    '         let checks=checks+1',
                                    '         if [[ $checks == 60 ]]; then',
                                    '           bigstart restart restnoded',
                                    '         fi',
                                    '         sleep 5',
                                    '      fi',
                                    '   done',
                                    '   if [[ $ready_response != *200 || $ready_response_declare != *204 ]]; then',
                                    '      error_exit "$LINENO: AS3 was not installed correctly. Exit."',
                                    '   fi',
                                    '}',
                                    'declare -a tmsh=()',
                                    'date',
                                    'echo \'starting custom-config.sh\'',
                                    'source /usr/lib/bigstart/bigip-ready-functions',
                                    'wait_bigip_ready',
                                    'tmsh+=(',
                                    '"tmsh load sys application template /config/cloud/f5.service_discovery.tmpl"',
                                    '"tmsh modify sys management-dhcp sys-mgmt-dhcp-config request-options delete { ntp-servers }"',
                                    '\'tmsh save /sys config\'',
                                    ')',
                                    'for CMD in "${tmsh[@]}"',
                                    'do',
                                    '    if $CMD;then',
                                    '        echo "command $CMD successfully executed."',
                                    '    else',
                                    '        error_exit "$LINENO: An error has occurred while executing $CMD. Aborting!"',
                                    '    fi',
                                    'done',
                                    '    wait_bigip_ready',
                                    '    date',
                                    '    ### START CUSTOM TMSH CONFIGURATION',
                                    '    mgmtGuiPort="' + str(context.properties['mgmtGuiPort']) + '"',
                                    '    passwd=$(f5-rest-node /config/cloud/gce/node_modules/@f5devcentral/f5-cloud-libs/scripts/decryptDataFromFile.js --data-file /config/cloud/gce/.adminPassword)',
                                    '    file_loc="/config/cloud/custom_config"',
                                    '    url_regex="^(https?|file)://[-A-Za-z0-9\+&@#/%?=~_|!:,.;]*[-A-Za-z0-9\+&@#/%=~_|]$"',
                                    '    if [[ ' + str(context.properties['declarationUrl']) + ' =~ $url_regex ]]; then',
                                    '       response_code=$(/usr/bin/curl -sk -w "%{http_code}" ' + str(context.properties['declarationUrl']) + ' -o $file_loc)',
                                    '       if [[ $response_code == 200 ]]; then',
                                    '           echo "Custom config download complete; checking for valid JSON."',
                                    '           cat $file_loc | jq .class',
                                    '           if [[ $? == 0 ]]; then',
                                    '               wait_for_ready',
                                    '               response_code=$(/usr/bin/curl -skvvu admin:$passwd -w "%{http_code}" -X POST -H "Content-Type: application/json" https://localhost:${mgmtGuiPort}/mgmt/shared/appsvcs/declare -d @$file_loc -o /dev/null)',
                                    '               if [[ $response_code == *200 || $response_code == *502 ]]; then',
                                    '                   echo "Deployment of custom application succeeded."',
                                    '               else',
                                    '                   echo "Failed to deploy custom application; continuing..."',
                                    '                   echo "Response code: ${response_code}"',
                                    '               fi',
                                    '           else',
                                    '               echo "Custom config was not valid JSON, continuing..."',
                                    '           fi',
                                    '       else',
                                    '           echo "Failed to download custom config; continuing..."',
                                    '           echo "Response code: ${response_code}"',
                                    '       fi',
                                    '    else',
                                    '       echo "Custom config was not a URL, continuing..."',
                                    '    fi',
                                    '### END CUSTOM TMSH CONFIGURATION',
                                    'EOF',
                                    'curl -s -f --retry 20 -o /config/cloud/f5-cloud-libs.tar.gz https://cdn.f5.com/product/cloudsolutions/f5-cloud-libs/v4.16.0/f5-cloud-libs.tar.gz',
                                    'curl -s -f --retry 20 -o /config/cloud/f5-cloud-libs-gce.tar.gz https://cdn.f5.com/product/cloudsolutions/f5-cloud-libs-gce/v2.4.0/f5-cloud-libs-gce.tar.gz',
                                    'curl -s -f --retry 20 -o /config/cloud/f5-appsvcs-3.5.1-5.noarch.rpm https://cdn.f5.com/product/cloudsolutions/f5-appsvcs-extension/v3.6.0/dist/lts/f5-appsvcs-3.5.1-5.noarch.rpm',
                                    'curl -s -f --retry 20 -o /config/cloud/f5.service_discovery.tmpl https://cdn.f5.com/product/cloudsolutions/iapps/common/f5-service-discovery/v2.3.2/f5.service_discovery.tmpl',
                                    'chmod 755 /config/verifyHash',
                                    'chmod 755 /config/installCloudLibs.sh',
                                    'chmod 755 /config/waitThenRun.sh',
                                    'chmod 755 /config/cloud/gce/custom-config.sh',
                                    'mkdir -p /var/log/cloud/google',
                                    CUSTHASH,
                                    'touch /config/cloud/gce/FIRST_BOOT_COMPLETE',
                                    'nohup /config/installCloudLibs.sh >> /var/log/cloud/google/install.log < /dev/null &',
                                    'nohup /config/waitThenRun.sh f5-rest-node /config/cloud/gce/node_modules/@f5devcentral/f5-cloud-libs/scripts/onboard.js --host localhost --signal ONBOARD_DONE --port 8443 --ssl-port ' + str(context.properties['mgmtGuiPort']) + ' -o /var/log/cloud/google/onboard.log --log-level ' + str(context.properties['logLevel']) + ' --license ' + str(context.properties['licenseKey1']) + ' --install-ilx-package file:///config/cloud/f5-appsvcs-3.5.1-5.noarch.rpm ' + ntp_list + timezone + ' --modules ' + PROVISIONING_MODULES + SENDANALYTICS + ' >> /var/log/cloud/google/install.log < /dev/null & ',                                    
                                    'nohup /config/waitThenRun.sh f5-rest-node /config/cloud/gce/node_modules/@f5devcentral/f5-cloud-libs/scripts/runScript.js --file /config/cloud/gce/custom-config.sh --cwd /config/cloud/gce -o /var/log/cloud/google/custom-config.log --wait-for ONBOARD_DONE --signal CUSTOM_CONFIG_DONE --log-level ' + str(context.properties['logLevel']) + ' >> /var/log/cloud/google/install.log < /dev/null &',
                                    'touch /config/startupFinished',
                                    'fi'
                                    ])
                            )
                }]
    }
    return metadata

def Outputs(context):
    output_ip_options = {
        'public': '.accessConfigs[0].natIP',
        'private': '.networkIP'
    }
    pub_or_priv = 'public' if str(context.properties['provisionPublicIP']).lower() == 'yes' else 'private'

    outputs = [{
        'name': 'region',
        'value': context.properties['region']
    },
    {
        'name': 'selfLink',
        'value': '$(ref.{}.selfLink)'.format('bigip1-' + context.env['deployment'])
    },
    {
        'name': 'mgmtURL',
        'value': 'https://$(ref.bigip1-' + context.env['deployment'] + '.networkInterfaces[0]' + output_ip_options[pub_or_priv] + '):' + str(context.properties['mgmtGuiPort'])
    },
    {
        'name': 'appTrafficAddress',
        'value': '$(ref.bigip1-' + context.env['deployment'] + '.networkInterfaces[0]' + output_ip_options[pub_or_priv] + ')'
    }]
    return outputs

def GenerateConfig(context):
    ## set variables

    # build resources
    resources = [
        Instance(context),
        FirewallRuleApp(context),
        FirewallRuleMgmt(context),
    ]
    outputs = Outputs(context)
    return {'resources': resources, 'outputs': outputs}