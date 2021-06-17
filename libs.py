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

def write_to_file(filename, data):
    #try:
    #    with open(filename, 'w', encoding = 'utf-8') as fout:
    #        fout.write(data)
    #    return True
    #except:
    #    return False
    with open(filename, 'w', encoding = 'utf-8') as fout:
        fout.write(data)

def read_from_file(filename):
    #with open(filename, 'r', encoding = 'utf-8') as file_in:
    #    file_contents = file_in.read()
    #    return file_contents
    if os.path.exists(filename):
        with open(filename, 'r', encoding = 'utf-8') as file_in:
            file_contents = file_in.read()
        return file_contents
    else:
        return False