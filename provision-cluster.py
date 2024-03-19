import argparse
import http.client
import json
import time
import os


parser = argparse.ArgumentParser()

parser.add_argument('--node-count', type=int, default=1,
                    help='number of nodes in cluster. can be 1,3,4,5....')
parser.add_argument('--node-type', choices=['b1', 'b2'],
                    default='medium', help='size of a node in the cluster')
parser.add_argument('--apikey',required=True)
parser.add_argument('--output', default='k8s.config',
                    help='name of file to save the configuration to')


args = parser.parse_args()


if args.node_count < 1 or args.node_count > 3:
    print('unsupported node count')
    exit(1)

node_count = args.node_count
node_type = args.node_type

req_headers = {'Authorization': f'Bearer {args.apikey}'}
try:
    conn = http.client.HTTPSConnection('api.sextillion.io')
    req_data = {'nodeCount': node_count, 'nodeType': node_type}
    
    conn.request('POST', '/sc/cluster', json.dumps(req_data),
                 headers=req_headers)
    hres = conn.getresponse()
    if hres.status != 200:
        print(f'failed to create cluster {hres.reason}')
        exit(1)

    res_body = hres.read().decode('utf-8')
    hres_data = json.loads(res_body)

    clusterId = hres_data["clusterId"]
    print(f'provisioning cluster {clusterId}')
    clusterIp = ''
    while hres_data['stage'] != 'k8sReady' or hres_data['stageIndex'] < 9:
        time.sleep(3)
        conn.request('GET', f'/sc/cluster/{clusterId}', headers=req_headers)
        hres = conn.getresponse()
        if hres.status == 200:
            res_body = hres.read().decode('utf-8')
            hres_data = json.loads(res_body)

            if hres_data['nodes']:
                clusterIp=hres_data['nodes'][0]['ip']

        elif (hres.status == 404):
            print(f'cluster {clusterId} not found')
            exit(1)
        else:
            hres_data['stage'] = 'unknown'
            print(f'failed to fetch cluster info {hres.status}')

        print(f'cluster {clusterId} stage {int(round((hres_data["stageIndex"]/9)*100,0))}%')

    if hres_data['stage'] == 'k8sReady':
        conn.request(
            'GET', f'/sc/cluster/{clusterId}/kubeconfig', headers=req_headers)
        hres = conn.getresponse()
        if (hres.status == 200):
            fileContent = hres.read()
            with open(args.output, 'wb') as file:
              file.write(fileContent)
            
            output_file=os.environ.get('GITHUB_OUTPUT') if os.environ.get('GITHUB_OUTPUT') else 'clusterId.txt'
            with open(output_file,'at') as file:
              file.write(f'clusterId={clusterId}\n')
              file.write(f'clusterIp={clusterIp}\n')
        else:
            print('failed to fetch configuration', hres.status)
            exit(1)
    else:
        print('failed to start cluster last known status', hres_data['stage'])
        exit(1)
    
except Exception as ex:
    print('failed to deploy cluster', ex)
    exit(1)
