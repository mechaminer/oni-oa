import subprocess 
import json
import time, os
import struct, socket
import numpy as np
import xml.etree.ElementTree as ET
import sys
import linecache, bisect
import getopt
import shutil

def ip_to_int(ip):
    o = map(int, ip.split('.'))
    res = (16777216 * o[0]) + (65536 * o[1]) + (256 * o[2]) + o[3]
    return res

def check_if_ip_is_internal(ip, ranges):
    for r in ranges:
        if(ip_to_int(ip) >= r[0] and ip_to_int(ip) <= r[1]):
            return 1
    return 0

def get_geo_ip(ip,iploc, iplist):
    result = ''
    if ip.strip() != "" and ip != None:
        result = linecache.getline(iploc, bisect.bisect(iplist,ip_to_int(ip))).replace('\n','')
    return result

def get_gti_rep(ip,gti_command=''):
    reputation = -1
    try:
        response_json = subprocess.check_output(gti_command.replace('###IP###', ip), shell=True)
        result_dict = json.loads(response_json[0:len(response_json) - 1])
        reputation = result_dict['a'][0]['rep']
        reputation = int(reputation)
    except Exception, err:
        print err
        reputation = -1
    
    return str(reputation)

def get_norse_rep(ip, norse_command=''):
    reputation = -1
    try:
        response = subprocess.check_output(norse_command.format(norse_api_key, ip, NORSE_URL), shell=True)
        # the executed curl command returns an XML as response 
        root_element = ET.fromstring(response)
        reputation = root_element.find("./response/risk_name").text
    except:
        #reputation = -1        
        reputation = "Low"
    return reputation
    
def main():

    iploc = '/{0}/ipython/iploc/iploc.csv'
    network_context_file = '/{0}/ipython/iploc/IP_Ranges.csv'
    date = ''
    userDir = ''
    flow = False
    dns = False

    #------------------- GTI Integration----------------------------#

    #This script assumes that GTI Rest client is alreay installed and in the following path
    rest_client_path = '/{0}/refclient/restclient'
    gti_server = ''
    gti_password = ''
    gti_user = ''

    
    #--------------- Norse Integration ----------------------------#
    # Assuming the client already has a Norse license

    norse_api_key = ''
    NORSE_URL = 'http://us.api.ipviking.com/api/'
    norse_command = 'curl -d apikey={0} -d method=ipview -d ip={1} {2}'

    sconnects_path = '/{0}/ipython/user/{1}/'

    if not os.path.isfile('./gtiConfig.json'):
        print "GTI Config file not found. the gtiConfig.json file should be in the same folder as this script"
    else:
        config = json.load(open('./gtiConfig.json'))
        gti_server = config['gti_server']
        gti_user = config['gti_user']
        gti_password = config['gti_password']
	gti_ci = config['gti_ci']
    
    if not os.path.isfile('./norseConfig.json'):
        print "Norse Config file not found. the norseConfig.json file should be in the same folder as this script"
    else:
        config = json.load(open('./norseConfig.json'))
        norse_api_key = config['norse_api_key']

    try:
        opts, args = getopt.getopt(sys.argv[1:], 'hd:u:', ['help', 'date=', 'user=', 'flow', 'dns'])
    except getopt.GetoptError as err:
        print 'usage: python <script.py> -d <20150807> -u <duxbury> [--flow OR --dns]'
        print 'usage: python <script.py> --date <20150807> --user <duxbury> [--flow OR --dns]'
        sys.exit(2)

    if '--flow' in opts and '--dns' in opts:
        print 'Error: detected --flow and --dns in same command execution, please choose just one option.'
        print 'Usage: lda_ranking.py -d <date(yyyymmdd)> -u <userDir> -l <3000> -i <inputFile.csv> -o <outputFile.csv> [--flow OR --dns]'

        sys.exit(2)

    for opt, arg in opts:
        if opt in ('-h', '--help'):
            print 'usage: python <script.py> -d <20150807> -u <duxbury> [--flow OR --dns]'
            print 'usage: python <script.py> --date <20150807> --user <duxbury> [--flow OR --dns]'
            sys.exit()
        elif opt in ('-d', '--date'):
            date = arg
        elif opt in ('-u', '--user'):
            if arg[0] == '/':
                arg = arg[1:]
            userDir = arg
        elif opt == '--flow':
            flow = True
        elif opt == '--dns':
            dns = True
    
    if flow == False and dns == False:
        print 'INFO: no --flow or --dns options detected. The script will use flow by default'
        flow = True

    flow_config = None
    dns_config = None

    if flow and os.path.isfile('./ldaFlowConfig.json'):
        flow_config = json.load(open('./ldaFlowConfig.json'))
    elif flow:
        print 'Could not find ldaFlowConfig.json file please make sure that it is at the same path as this script.'
        sys.exit(2)

    if dns and os.path.isfile('./ldaDnsConfig.json'):
        dns_config = json.load(open('./ldaDnsConfig.json'))
    elif dns:
        print 'Could not find ldaDnsConfig.json file please make sure that it is at the same path as this script.'
        sys.exit(2)

    iploc = iploc.format(userDir)
    rest_client_path = rest_client_path.format(userDir)
    sconnects_path = sconnects_path.format(userDir, date)
    network_context_file = network_context_file.format(userDir)    
    lda_file = sconnects_path
    lda_bu = sconnects_path 
    lda_temp = sconnects_path 
    
    if flow:
        lda_file += 'flow_scores.csv'
        lda_bu += 'flow_scores_bu.csv'
        lda_temp += 'flow_scores_temp.csv'
    elif dns:
        lda_file += 'dns_scores.csv'
        lda_bu += 'dns_scores_bu.csv'
        lda_temp += 'dns_scores_temp.csv'

    gti_command = "{0} -s {1} -q \'{2}\' -i {3} -p \'{4}\' -t".format(rest_client_path, gti_server, gti_ci, gti_user, gti_password)

    ip_ranges = []

    #------- First Add the network Context--------------------#
    
    ip_dict = {}

    new_content_lines = []
    temp_lines = []

    src_ip_index = 0
    dst_ip_index = 0
    dns_a_ip_index = 0

    if flow and flow_config != None:
        src_ip_index = flow_config['lda_file_schema']['srcIP']
        dst_ip_index = flow_config['lda_file_schema']['dstIP']
    
    if dns and dns_config != None:
        src_ip_index = dns_config['lda_file_schema']['ip_src']
        dst_ip_index = dns_config['lda_file_schema']['ip_dst']
        dns_a_ip_index = dns_config['lda_file_schema']['dns_a']

    with open(lda_file, 'rb') as f:
        for line in f:
            line_parts = line.split(',')
            src_ip = line_parts[src_ip_index]
            dst_ip = line_parts[dst_ip_index]
            
            if dns:
                dns_a_ip = line_parts[dns_a_ip_index]
                if not dns_a_ip in ip_dict:
                    ip_dict[dns_a_ip] = {}

            if not src_ip in ip_dict:
                ip_dict[src_ip] = {}
            if not dst_ip in ip_dict:
                ip_dict[dst_ip] = {}

            new_content_lines.append(line)

    header = new_content_lines[0].strip() + ',srcIpInternal,destIpInternal'
    
    if not os.path.isfile(network_context_file):
        print "Network context csv file not found at: " + network_context_file
	temp_lines = map(lambda line: line.strip()+",,",new_content_lines[1:])
	new_content_lines = [header] + temp_lines                                        
    else:
        print "Adding IP Context..."
        with open(network_context_file, 'rb') as f:
            ip_ranges += map(lambda line: (ip_to_int(line.split(',')[0]),ip_to_int(line.split(',')[1])),f)        
        for line in enumerate(new_content_lines[1:]): 
	    line_parts = line.split(',')
	    src_ip = line_parts[src_ip_index]
	    dst_ip = line_parts[dst_ip_index]
	    is_src_ip_internal = check_if_ip_is_internal(src_ip, ip_ranges)
	    is_dst_ip_internal = check_if_ip_is_internal(dst_ip, ip_ranges)
            if src_ip in ip_dict:
		ip_dict[src_ip]['isInternal'] = is_src_ip_internal
            if dst_ip in ip_dict:
		ip_dict[dst_ip]['isInternal'] = is_dst_ip_internal

	    temp_lines.append(line.strip() + ',' + str(is_src_ip_internal) + ',' + str(is_dst_ip_internal))
	
	new_content_lines = [header] + temp_lines
    
    temp_lines = []
    
    if flow:
	header = new_content_lines[0].strip() + ',srcGeo,dstGeo,srcDomain,dstDomain'
    elif dns:
	header = new_content_lines[0].strip() + ',dnsAGeo,dnsADomain'

    if not os.path.isfile(iploc):
        print "IP location file not found at: " + iploc
	if flow:
	    temp_lines = map(lambda line: line.strip() + ",,,,",new_content_lines[1:])
	elif dns:
	    temp_lines = map(lambda line: line.strip() + ",,", new_content_lines[1:])
	new_content_lines = [header] + temp_lines
    else:        
        print 'loading IP location context...'
        iplist = np.loadtxt(iploc,dtype=np.uint32,delimiter=',',usecols={0},converters={0: lambda s: np.uint32(s.replace('"',''))})
        print 'Adding Geo Location context...'
        for line in enumerate(new_content_lines[1:]):            
            if flow:
		line_parts = line.split(',')
                src_ip = line_parts[src_ip_index]
                dst_ip = line_parts[dst_ip_index]

                src_geo = ";".join(get_geo_ip(src_ip,iploc, iplist).replace('"','').split(',')[4:6])+ " " + ";".join(get_geo_ip(src_ip, iploc, iplist).replace('"','').split(',')[8:9])
                dst_geo = ";".join(get_geo_ip(dst_ip, iploc, iplist).replace('"','').split(',')[4:6]) + " " + ";".join(get_geo_ip(dst_ip, iploc, iplist).replace('"','').split(',')[8:9])

                src_domain = get_geo_ip(src_ip, iploc, iplist).replace('"','').split(',')[9:10][0]
                dst_domain = get_geo_ip(dst_ip, iploc, iplist).replace('"','').split(',')[9:10][0]

                ip_dict[src_ip]['geo'] = src_geo
                ip_dict[src_ip]['domain'] = src_domain

                ip_dict[dst_ip]['geo'] = dst_geo
                ip_dict[dst_ip]['domain'] = dst_domain

                temp_lines.append(line.strip() + ',' + ip_dict[src_ip]['geo'] + ',' + ip_dict[dst_ip]['geo'] + ',' + ip_dict[src_ip]['domain'] + ',' + ip_dict[dst_ip]['domain'])

	    elif dns:
		dns_a_column_index = dns_config['lda_file_schema']['dns_a']             
                line_parts = line.split(',')                    
                dns_a_ip = line_parts[dns_a_column_index]      
                  
                dns_a_geo = ''
                dns_a_domain = ''

                if dns_a_ip.strip() != '':
		    dns_a_geo = ";".join(get_geo_ip(dns_a_ip, iploc, iplist).replace('"','').split(',')[4:6])+ " " + ";".join(get_geo_ip(dns_a_ip, iploc, iplist).replace('"','').split(',')[8:9])                    
		    dns_a_domain = get_geo_ip(dns_a_ip, iploc, iplist).replace('"','').split(',')[9:10][0]
                    
                ip_dict[dns_a_ip]['geo'] = dns_a_geo
                ip_dict[dns_a_ip]['domain'] = dns_a_domain                
                 
                temp_lines.append(line.strip() + ',' + ip_dict[dns_a_ip]['geo'] + ',' + ip_dict[dns_a_ip]['domain'])
	
	new_content_lines = [header] + temp_lines

    temp_lines = []
    header = new_content_lines[0].strip() +  ',gtiSrcRep,gtiDstRep'
 
    
    if gti_server == '' or gti_password == '' or gti_user == '':
        print 'More than one GTI Config values are empty, Can\'t add GTI reputation '
        temp_lines = map(lambda line: line.strip() + ",,", new_content_lines[1:])
	new_content_lines = [header] + temp_lines
    else:
        for line in enumerate(new_content_lines[1:]):            
            if flow:
                line_parts = line.split(',')
                src_ip = line_parts[2]
                dst_ip = line_parts[3]

                if 'gti_rep' not in ip_dict[src_ip]:
		    ip_dict[src_ip]['gti_rep'] = get_gti_rep(src_ip, gti_command)

                if 'gti_rep' not in ip_dict[dst_ip]:
		    ip_dict[dst_ip]['gti_rep'] = get_gti_rep(dst_ip, gti_command)

                temp_lines.appned(line.strip() + ',' + ip_dict[src_ip]['gti_rep'] + ',' + ip_dict[dst_ip]['gti_rep'])

        new_content_lines = [header] + temp_lines
    
    temp_lines = []
    header = new_content_lines[0].strip() + ',norseSrcRep,norseDstRep'

    if norse_api_key == '' or norse_url == '':
        print 'Norse Configurations missing values, Can\'t add Norse Reputation'
        if flow:
	    temp_lines = map(lambda line: line.strip() + ',,'
	    new_content_lines = [header] + temp_lines
    else:
        for line in enumerate(new_content_lines[1:]):
            if flow:
                line_parts = line.split(',')
                src_ip = line_parts[2]
                dst_ip = line_parts[3]

                if 'norse_rep' not in ip_dict[src_ip]:
                    ip_dict[src_ip]['norse_rep'] = get_norse_rep(src_ip, norse_command)
                if 'norse_rep' not in ip_dict[dst_ip]:
                    ip_dict[dst_ip]['norse_rep'] = get_norse_rep(dst_ip, norse_command)

                temp_lines.append(line.strip() + ',' + ip_dict[src_ip]['norse_rep'] + ',' + ip_dict[dst_ip]['norse_rep']
	new_content_lines = [header] + temp_lines
                
    new_content = '\n'.join(new_content_lines)
    
    if new_content != '':
        f = open(lda_bu, 'wb')
        f.write(new_content)
        f.close()

        f2 = open(lda_file, 'wb')
        f2.write(new_content)
        f2.close()

main()
