#!/usr/bin/env python3
# Simple script to control NVIDIA GPU fan speeds using a custom curve
#
# Made by Jack'lul <jacklul.github.io>
#
# NVML docs:
#  https://github.com/NVIDIA/nvidia-settings/blob/main/src/nvml.h
#  https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceQueries.html
#  https://docs.nvidia.com/deploy/nvml-api/group__nvmlDeviceCommands.html
#
# pynvml docs:
#  https://pypi.org/project/nvidia-ml-py/

import os
import time
import argparse
import signal

try:
    from pynvml import *
except ModuleNotFoundError:
    print(f"Error: Module 'nvidia-ml-py' not found - please install it using 'pip install nvidia-ml-py', you might also be able to find it in your package manager", file=sys.stderr)
    exit(1)

################################

def arg_types(parser):
    arg_types = {}

    for action in parser._actions:
        if action.dest != 'help':
            if action.type == None and type(action.default) == bool:
                arg_types[action.dest] = bool
            else:
                arg_types[action.dest] = action.type or str

    return arg_types

def load_env(file_path):
    with open(file_path, 'r') as file:
        for line in file:
            line = line.strip()
            if line and not line.startswith('#'):
                key, value = line.split('=', 1)
                if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
                    value = value[1:-1]
                os.environ[key] = value

def convert_value(value, target_type):
    try:
        if target_type == bool and not type(value) == bool:
            return value.lower() in ['true', '1', 'yes', 'y']
        if target_type == str and value == None:
            value = ''

        return target_type(value)
    except (ValueError, TypeError):
        return value

def assign_env_values(args, types, exclude = []):
    for arg_name, arg_type in types.items():
        if arg_name in exclude or arg_name == 'help':
            continue
        env_var_name = arg_name.upper()
        current_value = getattr(args, arg_name)
        new_value = os.getenv(env_var_name, current_value)
        new_value = convert_value(new_value, arg_type)
        setattr(args, arg_name, new_value)

    return args

def parse_version(version):
    return int(version.replace('.', ''))

def compare_versions(version1, version2):
    v1 = parse_version(version1)
    v2 = parse_version(version2)

    if v1 < v2:
        return False

    return True

def create_interrupt_handler(variable):
    def interrupt_handler(sig, frame):
        variable['running'] = False
    return interrupt_handler

def validate_args(args):
    if args.curve:
        pairs = args.curve.split(',')
        invalid = False
        if len(pairs) < 1:
            invalid = True
        for pair in pairs:
            if ':' not in pair:
                invalid = True
    else:
        invalid = True

    if invalid:
        print("Error: Curve must contain at least one point in the format 'temperature:speed,...'", file=sys.stderr)
        exit(1)

    if not args.sleep > 0:
        print("Error: Sleep time must be bigger than 0", file=sys.stderr)
        exit(1)

def parse_fan_curve(fan_curve):
    speed_curve = {}
    temp_points = []
    curve_array = fan_curve.split(',')

    for element in curve_array:
        temp, speed = element.split(':')
        temp = int(temp)
        speed = int(speed)
        speed_curve[temp] = speed
        temp_points.append(temp)

    temp_points.sort()
    return speed_curve, temp_points

def interpolate_speed(temp, speed_curve, temp_points, min_temp, min_speed):
    if temp < min_temp:
        return min_speed

    for i in range(1, len(temp_points)):
        if temp < temp_points[i]:
            prev_temp = temp_points[i - 1]
            next_temp = temp_points[i]
            prev_speed = speed_curve[prev_temp]
            next_speed = speed_curve[next_temp]
            delta_temp = next_temp - prev_temp
            delta_speed = next_speed - prev_speed
            temp_diff = temp - prev_temp
            interpolated_speed = prev_speed + (temp_diff * delta_speed // delta_temp)
            return interpolated_speed

    return speed_curve[temp_points[-1]]

def set_gpu_fan_policy(handle, fans = 1, manual = False):
    for i in range(fans):
        if manual:
            nvmlDeviceSetFanControlPolicy(handle, i, NVML_FAN_POLICY_MANUAL)
        else:
            nvmlDeviceSetFanControlPolicy(handle, i, NVML_FAN_POLICY_TEMPERATURE_CONTINOUS_SW)

def set_gpu_fan_speed(handle, fans = 1, speed = 50):
    if speed > 0:
        for i in range(fans):
            nvmlDeviceSetFanSpeed_v2(handle, i, speed)
    else:
        set_gpu_fan_policy(handle, fans, False)

def main():
    parser = argparse.ArgumentParser(
        description="Fan curve script using official NVML API",
        epilog='',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument('-e', '--env', type=str, help='env file to load', default=None)
    parser.add_argument('-i', '--index', type=int, help='device index', default=0)
    parser.add_argument('-u', '--uuid', type=str, help='device UUID', default=None)
    parser.add_argument('-c', '--curve', type=str, help='fan curve points, in format "temperature:speed,..."', default=None)
    parser.add_argument('-y', '--hysteresis', type=int, help='temperature hysteresis (down only)', default=0)
    parser.add_argument('-s', '--sleep', type=float, help='sleep time in main loop', default=1)
    parser.add_argument('-v', '--verbose', action='store_true', help='show verbose messages', default=False)
    parser.add_argument('-t', '--test', action='store_true', help='do not execute control commands', default=False)

    args = parser.parse_args()
    types = arg_types(parser)

    if not args.env == None:
        load_env(args.env)

    args = assign_env_values(args, types, ['env'])
    validate_args(args)

    if os.getenv('INVOCATION_ID') or os.getenv('JOURNAL_STREAM'):
        args.verbose = False

    if args.verbose:
        print(args)

    speed_curve, temp_points = parse_fan_curve(args.curve)
    min_temp = temp_points[0]
    #max_temp = temp_points[len(temp_points) - 1]
    min_speed = speed_curve[min_temp]
    #max_speed = max(speed_curve.values())

    nvmlInit()

    try:
        required_nvml_version = "11.520.56"  # https://github.com/NVIDIA/nvidia-settings/blob/f213c7bddff91634e6c4d9681e8a9a1b9883db88/src/nvml.h
        if not compare_versions(nvmlSystemGetNVMLVersion(), required_nvml_version):
            print(f"You need at least NVML version {required_nvml_version} to use this script")
            exit(1)

        if args.uuid != '':
            handle = nvmlDeviceGetHandleByUUID(args.uuid)
        else:
            handle = nvmlDeviceGetHandleByIndex(args.index)

        if args.test:
            print("Running in test mode - no control commands will be executed")

        name = nvmlDeviceGetName(handle)
        uuid = nvmlDeviceGetUUID(handle)
        fans = nvmlDeviceGetNumFans(handle)

        print(f"Detected {name} ({uuid}) with {fans} fans")

        #min_fan_speed, max_fan_speed = nvmlDeviceGetMinMaxFanSpeed(handle)  # This is currently broken in NVIDIA's python lib?
        #if min_speed < min_fan_speed or max_speed > max_fan_speed:
        #    print(f"Warning: Allowed fan speed range is {min_fan_speed}-{max_fan_speed}%", file=sys.stderr)

        #set_gpu_fan_policy(handle, fans, true)  # Not required as calling nvmlDeviceSetFanSpeed_v2 enforces manual mode

        print(f"Running main loop (sleep = {args.sleep})...")

        state = {'running': True}
        control_temp = 0

        signal.signal(signal.SIGINT, create_interrupt_handler(state))
        signal.signal(signal.SIGTERM, create_interrupt_handler(state))

        while state['running']:
            gpu_temp = nvmlDeviceGetTemperature(handle, NVML_TEMPERATURE_GPU)
            fan_speed = nvmlDeviceGetFanSpeed(handle)

            #DEBUG
            #with open('debug-temp.txt', 'r') as file:
            #    gpu_temp = int(file.read().strip())

            if args.hysteresis > 0 and gpu_temp > 50:  # Hysteresis at 50 and below doesn't make any sense
                if gpu_temp > control_temp or gpu_temp <= control_temp - args.hysteresis:
                    control_temp = gpu_temp
            else:
                control_temp = gpu_temp

            target_fan_speed = interpolate_speed(control_temp, speed_curve, temp_points, min_temp, min_speed)

            if fan_speed != target_fan_speed:
                if not args.test:
                    set_gpu_fan_speed(handle, fans, target_fan_speed)

                    if args.verbose:
                        print(f"Temperature = {gpu_temp}C, Fan speed = {target_fan_speed}%")
                else:
                    print(f"Would set fan speed to {target_fan_speed}% ({gpu_temp}C)")

            time.sleep(args.sleep)
    finally:
        if not args.test:
            set_gpu_fan_policy(handle, fans or 1, False)

        nvmlShutdown()

if __name__ == "__main__":
    main()
