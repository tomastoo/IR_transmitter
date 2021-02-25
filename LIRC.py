import lirc
import socket
import serial
import xml.etree.ElementTree as ET
import time
import pause


def get_lirc_client(ip, port, timeout):
    client = lirc.Client(
        connection=lirc.LircdConnection(
            address=(ip, port),
            socket=socket.socket(socket.AF_INET, socket.SOCK_STREAM),
            timeout=timeout
        )
    )
    return client


# get_confirm_code --> gets confirmation code of the specified command and returns it
# args:
#   if the command is a toggle one, like KEY_POWER for e.g, then toggle arg must be specified to
#   get the appropriate confirmation.
def get_confirm_code(command_name, config_xml):
    confirmation_codes = config_xml.find('confirmation_codes')
    for command in confirmation_codes.findall('command'):
        # print(command.get('name'), command.text)
        if command_name == command.get('name'):
            if command.get('toggle') == 'false':
                return command.text
            if command.get('toggle') == 'true':
                toggle_options = command.findall('toggle_option')

                if toggle_options is None or len(toggle_options) < 2:
                    raise Exception('command was set as toggle but no on and off option were found :' + command_name)
                else:
                    return toggle_options
            else:
                raise Exception('Configuration Format Error on command ' + command_name)

    raise Exception('Confirmation code not found in pulga_ir_config.xml for command ' + command_name)


def config_schedule_parser():
    print()


# send_command --> sends IR command, repeats until usb serial confirmation
# returns bool:
#        true --> command send successfully and confirmation received
#        false -->confirmation was never found or another error occurred

def send_command(lirc_client, serial_socket, config_xml, command, toggle_option=''):
    j = 0
    delays_and_tries = get_delay_and_tries(config_xml)

    remote = get_remote_name(config_xml)
    usb_serial_skip_lines = get_skip_lines()
    confirm_code = get_confirm_code(command, config_xml)
    source_confirm = ""
    source_line = ""

    toggle_wanted_confirmation = ''
    toggle_unwanted_confirmation = ''

    # if it is a toggle then i want to fill the toggle variables above
    if not isinstance(confirm_code, str):
        for toggle_opt in confirm_code:
            if toggle_opt.get('name') == toggle_option:
                toggle_wanted_confirmation = toggle_opt.text
            else:
                toggle_unwanted_confirmation = toggle_opt.text

    while j < delays_and_tries["ir_tries"]:
        try:
            j += 1
            serial_socket.flushInput()
            lirc_client.send_once(remote, command, repeat_count=1)
            i = 0
            # time.sleep(1)
            while i < delays_and_tries["serial_tries"]:
                try:
                    line_bytes = serial_socket.readline()
                    line_string = line_bytes.decode()

                    # if there is the possibility of having the tv kernel bursting the same message
                    # we want to ignore it
                    if is_skip_line(line_string, usb_serial_skip_lines):
                        continue

                    i += 1

                    # if it is not a toggle we just want to search for the confirmation code
                    if isinstance(confirm_code, str):
                        if confirm_code in line_string:
                            time.sleep(0.5)
                            return True
                        else:
                            print(line_string)
                    # but if it is a toggle we want to search for both confirmations but if we find the unwanted
                    # one then we need to repeat the command (works becuase its is a toggle)
                    else:
                        if toggle_wanted_confirmation in line_string:
                            print('TOGGLE WANTED = ' + line_string)
                            print(i)
                            time.sleep(delays_and_tries["toggle_delay"])
                            return True
                        # se encontrarmos outra vez
                        elif toggle_unwanted_confirmation in line_string:
                            print('TOGGLE UNWANTED = ' + line_string)
                            print(i)
                            time.sleep(delays_and_tries["toggle_delay"])
                            j -= 1
                            break

                except Exception as instance:
                    print(instance)

        except Exception as instance:
            print(instance)

    return False


# this function is needed in case that the tv kernel starts bursting printing errors or other messages.
# gets skip lines on xml configuration to avoid it
def get_skip_lines():
    try:
        tree = ET.parse('pulga_ir_config.xml')
        root = tree.getroot()
        tv_name = root.find("chosen_tv")
        tv = root.find(tv_name.text)
        usb_serial_skip = tv.find("usb_serial_skip")
        return usb_serial_skip.findall('line')

    except Exception as instance:
        return ""


def is_skip_line(line, skip_lines):
    is_skip = False
    if not isinstance(skip_lines, str):
        for skip_line in skip_lines:
            if skip_line.text in line:
                is_skip = True

    return is_skip


# IMPORTANT RESTRITION:
#   if the tv_kernel does not print the source confirmation after the confirmation for the command that will print
#       the current source then this function will not work
#   in the case of the Samsung BE43T-H it is always after so we gucci
def get_source(config_xml, serial_socket):
    delay_and_tries = get_delay_and_tries(config_xml)
    xml_tv_state = config_xml.find("TV_State")
    xml_get_source = xml_tv_state.find("get_source")
    source_confirmation = xml_get_source.find("confirmation").text
    source_code_list = xml_tv_state.findall("source")

    i = 0

    while i < delay_and_tries["serial_tries"]:
        try:
            line_bytes = serial_socket.readline()
            line_string = line_bytes.decode()
            if source_confirmation in line_string:
                for source_code in source_code_list:
                    if source_code.text in line_string:
                        return source_code.get('name')

        except Exception as instance:
            print(instance)
            continue

    raise Exception("No source was found")


def get_chosen_tv_config():
    root = get_tv_config_root()
    tv_name = root.find("chosen_tv")
    tv = root.find(tv_name.text)
    return tv


def get_tv_config_root():
    tree = ET.parse('pulga_ir_config.xml')
    root = tree.getroot()
    return root


def change_source(source, config_xml, serial_socket, lirc_client):
    logical_commands = config_xml.find("logical_commands")
    xml_tv_state = config_xml.find("TV_State")
    xml_get_source = xml_tv_state.find("get_source")
    xml_source_get_command = xml_get_source.find("command")

    # if the command that gets the source is a toggle button then we split command:toggle_option and feed it to
    #   the send_command
    if xml_source_get_command.get('toggle') == 'true':
        source_get_command_str = xml_source_get_command.text
        source_command_w_toggle = source_get_command_str.split(":")
        send_command(lirc_client, serial_socket, config_xml, source_command_w_toggle[0]
                     , toggle_option=source_command_w_toggle[1])

    else:
        source_get_command_str = xml_source_get_command.text
        send_command(lirc_client, serial_socket, config_xml, source_get_command_str)

    tv_source = get_source(config_xml, serial_socket)
    print(tv_source)
    if tv_source == source:
        return

    command_sequence = None

    try:
        for command in logical_commands:
            if command.get('type') == "source" and command.get('name') == source:
                source_origins = command.findall('from')
                for source_origin in source_origins:
                    if source_origin.get('name') == tv_source:
                        command_sequence = source_origin.text

    except Exception as instance:
        print(instance)

    if command_sequence is None:
        raise Exception("No command sequence was found in configuration xml")

    else:
        command_sequence_list = command_sequence.split(':')
        for command in command_sequence_list:
            send_command(lirc_client, serial_socket, config_xml, command)


def get_remote_name(config_xml):
    return config_xml.find('LIRC_remote').text


# returns dictionary with every delay and number of tries for send_command
def get_delay_and_tries(config_xml):
    delays_and_tries = {}

    delays_and_tries.update({"toggle_delay": int(config_xml.find('toggle_delay').text)})
    delays_and_tries.update({"ir_tries": int(config_xml.find('ir_tries').text)})
    delays_and_tries.update({"serial_tries": int(config_xml.find('serial_tries').text)})

    return delays_and_tries


def test(lirc_client, serial_socket, config_xml):
    send_command(lirc_client, serial_socket, config_xml, command="KEY_POWER", toggle_option='off')
    #change_source('HDMI_1', config_xml, serial_socket, lirc_client)


def main():
    tv_config_xml = get_chosen_tv_config()
    config_xml = get_tv_config_root()

    usb_serial_config = config_xml.find('usb_serial')
    com_port = usb_serial_config.find('port').text
    baud_rate = int(usb_serial_config.find('baud_rate').text)

    lirc_config = config_xml.find('lirc')
    lirc_ip = lirc_config.find('ip').text
    lirc_port = int(lirc_config.find('port').text)
    lirc_timeout = int(lirc_config.find('timeout').text)

    ser = serial.Serial(com_port, baud_rate)
    lirc_client = get_lirc_client(lirc_ip, lirc_port, lirc_timeout)

    test(lirc_client, ser, tv_config_xml)
    ser.close()
    # c = get_confirm_code('KEY_POWER')


main()
