
import logging, argparse, sys, json, os
#from time import sleep
from panos import check_if_panos_is_ready, panos_configure_admin_acct, panos_send_commands, panos_create_apikey, panos_create_vm_auth_key, create_bootstrap_terraform_files, panos_commit
#from libs import convert_xml_to_dict, write_to_file, read_from_file

TMP_FILE = 'tracker.tmp'

logging.basicConfig(format='%(asctime)s %(levelname)-8s %(message)s', level=logging.WARN)

parser = argparse.ArgumentParser()
parser.add_argument("--ip", help="IP address of PAN-OS device")
parser.add_argument("--login-username", help="Username to log in with")
parser.add_argument("--login-password", help="Password to use")
parser.add_argument("--priv-ssh-key", help="Path to ssh private key file")
parser.add_argument("--change-password-to", help="Set password")
parser.add_argument("--create-bootstrap", help="Creates bootstrap folder structure and necessary files for students")
parser.add_argument("--panorama-serial-number", help="Serial number for Panorama registration")
parser.add_argument("--create-api-key", help="Creates API key for PAN-OS device", action="store_true")
parser.add_argument('--current-student-number', help=argparse.SUPPRESS)

args = parser.parse_args()

def main():

    if args.current_student_number:
        current_student_number = int(args.current_student_number)

    panos_connection = None

    if args.ip:
        ip = args.ip

    if args.priv_ssh_key:
        use_keys = True
        key_file = args.priv_ssh_key
    else:
        use_keys = False
        key_file = ''

    if args.login_username:
        username = args.login_username
    else:
        username = 'admin'

    if args.login_password:
        password = args.login_password
    else:
        password = 'admin'

    if args.change_password_to:
        new_password = args.change_password_to

    if 'ip' in locals() and 'username' in locals():
        panos_connection = check_if_panos_is_ready(ip=ip, username=username, password=password, use_keys=use_keys, key_file=key_file)

    if 'new_password' in locals():
        panos_configure_admin_acct(panos_connection, new_password=new_password)
        password = new_password # password has been changed, so use the new_password moving forward.
        
    if 'ip' in locals():
        panos_send_commands(panos_connection, command_type='operational', commands=['show clock'])

    if args.panorama_serial_number:
        panos_send_commands(panos_connection, command_type='operational', commands=[f'set serial-number {args.panorama_serial_number}', 'request license fetch'])

    if args.create_api_key:
        panos_api_key = panos_create_apikey(username, password, ip)
        
    #if args.create_api_key and args.create_bootstrap:
    if args.create_bootstrap and 'ip' in locals():
        vm_auth_key = panos_create_vm_auth_key(ip, panos_api_key)
        create_bootstrap_terraform_files(current_student_number, vm_auth_key)

        panos_send_commands(panos_connection, command_type='operational', commands=['set cli scripting-mode on'])
        panos_send_commands(panos_connection, command_type='configure', commands=[
            'set deviceconfig system timezone US/Pacific',
            f"set deviceconfig system hostname Panorama-student-{current_student_number}",
            'set deviceconfig system dns-setting servers primary 1.0.0.1',
            'set deviceconfig system ntp-servers primary-ntp-server ntp-server-address pool.ntp.org'])
        panos_send_commands(panos_connection, command_type='configure', commands=[
            'set deviceconfig system device-telemetry threat-prevention no',
            'set deviceconfig system device-telemetry device-health-performance no',
            'set deviceconfig system device-telemetry product-usage no',
            'set deviceconfig system device-telemetry region americas',
            'set template sdwan-template config vsys vsys1',
            'set template sdwan-template config  deviceconfig system ',
            'set template-stack sdwan-stack templates sdwan-template',
            'set template-stack sdwan-stack settings default-vsys vsys1',
            'set template sdwan-template variable $wan1_ip type ip-netmask 1.1.1.1/32',
            'set template sdwan-template variable $wan2_ip type ip-netmask 1.1.1.2/32',
            'set template sdwan-template variable $wan1_next_hop type ip-netmask 1.1.1.1/32',
            'set template sdwan-template variable $wan2_next_hop type ip-netmask 1.1.1.2/32',
            'set template sdwan-template config  network profiles interface-management-profile Ping ping yes',
            'set template sdwan-template config  network interface ethernet ethernet1/1 layer3 ip $wan1_ip ',
            'set template sdwan-template config  network interface ethernet ethernet1/1 layer3 interface-management-profile Ping',
            'set template sdwan-template config  network interface ethernet ethernet1/2 layer3 ip $wan2_ip ',
            'set template sdwan-template config  network interface ethernet ethernet1/2 layer3 interface-management-profile Ping',
            'set template sdwan-template config  network interface ethernet ethernet1/3 layer3 dhcp-client',
            'set template sdwan-template config  network interface ethernet ethernet1/3 layer3 interface-management-profile Ping',
            'set template sdwan-template config  network virtual-router corp ecmp algorithm ip-modulo ',
            'set template sdwan-template config  network virtual-router corp interface [ ethernet1/1 ethernet1/2 ethernet1/3 ]'])
        panos_send_commands(panos_connection, command_type='configure', commands=[
            'set template sdwan-template config  vsys vsys1 import network interface [ ethernet1/1 ethernet1/2 ethernet1/3 ]',
            'set template sdwan-template config  vsys vsys1 zone Untrust network layer3 [ ]',
            'set template sdwan-template config  vsys vsys1 zone Trust network layer3 [ ]',
            'set template sdwan-template config  vsys vsys1 zone VPN network layer3 [ ]',
            'set template sdwan-template config  vsys vsys1 zone Untrust network layer3 [ ethernet1/1 ethernet1/2 ]',
            'set template sdwan-template config  vsys vsys1 zone Trust network layer3 ethernet1/3',
            'set template sdwan-template config  network virtual-router corp routing-table ip static-route net-198.18.0.0 nexthop ip-address $wan1_next_hop',
            'set template sdwan-template config  network virtual-router corp routing-table ip static-route net-198.18.0.0 path-monitor enable no',
            'set template sdwan-template config  network virtual-router corp routing-table ip static-route net-198.18.0.0 interface ethernet1/1',
            'set template sdwan-template config  network virtual-router corp routing-table ip static-route net-198.18.0.0 metric 10',
            'set template sdwan-template config  network virtual-router corp routing-table ip static-route net-198.18.0.0 destination 198.18.0.0/16',
            'set template sdwan-template config  network virtual-router corp routing-table ip static-route net-198.19.0.0 nexthop ip-address $wan2_next_hop',
            'set template sdwan-template config  network virtual-router corp routing-table ip static-route net-198.19.0.0 path-monitor enable no',
            'set template sdwan-template config  network virtual-router corp routing-table ip static-route net-198.19.0.0 interface ethernet1/2',
            'set template sdwan-template config  network virtual-router corp routing-table ip static-route net-198.19.0.0 metric 10',
            'set template sdwan-template config  network virtual-router corp routing-table ip static-route net-198.19.0.0 destination 198.19.0.0/16',
            'set device-group sdwan reference-templates sdwan-stack',
            'set device-group sdwan log-settings profiles default match-list traffic log-type traffic',
            'set device-group sdwan log-settings profiles default match-list traffic filter "All Logs"',
            'set device-group sdwan log-settings profiles default match-list traffic send-to-panorama yes',
            'set device-group sdwan log-settings profiles default match-list traffic quarantine no',
            'set device-group sdwan log-settings profiles default match-list threat log-type threat',
            'set device-group sdwan log-settings profiles default match-list threat filter "All Logs"',
            'set device-group sdwan log-settings profiles default match-list threat send-to-panorama yes',
            'set device-group sdwan log-settings profiles default match-list threat quarantine no',
            'set device-group sdwan log-settings profiles default match-list url log-type url',
            'set device-group sdwan log-settings profiles default match-list url filter "All Logs"',
            'set device-group sdwan log-settings profiles default match-list url send-to-panorama yes',
            'set device-group sdwan log-settings profiles default match-list url quarantine no',
            'set device-group sdwan log-settings profiles default match-list wildfire log-type wildfire',
            'set device-group sdwan log-settings profiles default match-list wildfire filter "All Logs"',
            'set device-group sdwan log-settings profiles default match-list wildfire send-to-panorama yes',
            'set device-group sdwan log-settings profiles default match-list wildfire quarantine no',
            'set device-group sdwan pre-rulebase security rules "permit all" target negate no',
            'set device-group sdwan pre-rulebase security rules "permit all" to any',
            'set device-group sdwan pre-rulebase security rules "permit all" from any',
            'set device-group sdwan pre-rulebase security rules "permit all" source any',
            'set device-group sdwan pre-rulebase security rules "permit all" destination any',
            'set device-group sdwan pre-rulebase security rules "permit all" source-user any',
            'set device-group sdwan pre-rulebase security rules "permit all" category any',
            'set device-group sdwan pre-rulebase security rules "permit all" application any',
            'set device-group sdwan pre-rulebase security rules "permit all" service any',
            'set device-group sdwan pre-rulebase security rules "permit all" source-hip any',
            'set device-group sdwan pre-rulebase security rules "permit all" destination-hip any',
            'set device-group sdwan pre-rulebase security rules "permit all" action allow',
            'set device-group sdwan pre-rulebase security rules "permit all" log-setting default'])
        panos_commit(panos_connection)

    if panos_connection:
        panos_connection.disconnect()

main()