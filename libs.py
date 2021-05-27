import http.client as hc
import xmltodict
import ssl, os

def make_http_request(host, url, **kwargs):
    if 'port' in kwargs:
        port = kwargs['port']
    else:
        port = 443

    try:
        httpcon = hc.HTTPSConnection(host, port, timeout = 10, context = ssl._create_unverified_context())
        httpcon.request('GET', url)
        return httpcon.getresponse().read()
    except Exception as e:
        print(f'An error occurred making http request: {e}')

def convert_xml_to_dict(xml_data):
    try:
        dictionary = xmltodict.parse(xml_data)
        return dictionary
    except:
        print('XML parsing response error occurred. (xml_to_dict)')

def create_bootstrap_folder_structure():
    paths = ['bootstrap/config', 'bootstrap/license', 'bootstrap/content', 'bootstrap/software']
    for path in paths: 
        os.makedirs(path, exist_ok=True)