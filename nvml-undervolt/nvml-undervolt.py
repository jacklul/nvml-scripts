#!/usr/bin/env python3
# Simple script to undervolt NVIDIA GPU using a hacky method
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
import math

try:
    from pynvml import *
except ModuleNotFoundError:
    print(f"Error: Module 'nvidia-ml-py' not found", file=sys.stderr)
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
    if not NVML_PSTATE_0 <= int(args.pstates) < NVML_PSTATE_15:
        print("Error: Invalid PSTATEs", file=sys.stderr)
        exit(1)

    if not args.target_clock > 0:
        print("Error: Target clock is not set", file=sys.stderr)
        exit(1)  

    if not args.transition_clock > 0:
        print("Error: Transition clock is not set", file=sys.stderr)
        exit(1)  

    if args.target_clock > 0 and args.transition_clock > 0 and args.transition_clock + 50 >= args.target_clock:
        print("Error: Target clock must be bigger than transition clock by more than 50", file=sys.stderr)
        exit(1)  

    if not args.core_offset > 0:
        print("Error: Core offset is not set", file=sys.stderr)
        exit(1)  

    if not args.sleep > 0:
        print("Error: Sleep time must be bigger than 0", file=sys.stderr)
        exit(1)

def get_step_mhz(clocks):
    clocks = clocks[0:3]
    differences = [clocks[i] - clocks[i + 1] for i in range(len(clocks) - 1)]
    return sum(differences) / len(differences)

def round_to_nearest_step(value, divisor):
    if value == 0:
        return 0

    if value % divisor == 0:
        nearest_value = (value // divisor) * divisor
    else:
        nearest_value = ((value // divisor) + 1) * divisor

    return math.ceil(nearest_value)

def interpolate_offset(value, offset, min_val, max_val, step_mhz):
    if value <= min_val:
        return 0
    elif value >= max_val:
        return offset
    else:
        scale = (value - min_val) / (max_val - min_val)
        scaled_offset = int(scale * offset)
        return round_to_nearest_step(scaled_offset, step_mhz)

def set_pstate_clocks(handle, clock_type, clock_offset, target_pstates):
    for pstate in range(0, target_pstates + 1):
        struct = c_nvmlClockOffset_t()
        struct.version = nvmlClockOffset_v1
        struct.type = clock_type
        struct.pstate = pstate
        struct.clockOffsetMHz = clock_offset
        nvmlDeviceSetClockOffsets(handle, struct)

def main():
    parser = argparse.ArgumentParser(
        description="Undervolt script using official NVML API",
        epilog='',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )

    parser.add_argument('-e', '--env', type=str, help='env file to load', default=None)
    parser.add_argument('-i', '--index', type=int, help='device index', default=0)
    parser.add_argument('-u', '--uuid', type=str, help='device UUID', default=None)
    parser.add_argument('-c', '--core-offset', type=int, help='core clock offset', default=0)
    parser.add_argument('-m', '--memory-offset', type=int, help='memory clock offset', default=0)
    parser.add_argument('-a', '--target-clock', type=int, help='target clock', default=0)
    parser.add_argument('-r', '--transition-clock', type=int, help='clock at which to toggle the changes', default=0)
    parser.add_argument('-l', '--curve', action='store_true', help='use linear curve mode', default=False)
    parser.add_argument('-n', '--curve-increment', type=float, help='linear curve increments', default=0)
    parser.add_argument('-k', '--clock-step', type=float, help='core clock step in MHz', default=0)
    parser.add_argument('-w', '--power-limit', type=int, help='power limit in watts (W)', default=0)
    parser.add_argument('-d', '--temperature-limit', type=int, help='temperature limit in celsius (C)', default=0)
    parser.add_argument('-p', '--pstates', type=int, help='pstates to apply to', default=0)
    parser.add_argument('-s', '--sleep', type=float, help='sleep time in main loop', default=0.5)
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

    nvmlInit()

    try:
        required_nvml_version = "12.555.42"  # https://github.com/NVIDIA/nvidia-settings/blob/b0807ed0b0280699f6fa1e5a1469fec1723f7b23/src/nvml.h
        if not compare_versions(nvmlSystemGetNVMLVersion(), required_nvml_version):
            print(f"You need at least NVML version {required_nvml_version} to use this script")
            exit(1)

        if not args.uuid == None and args.uuid != '':
            handle = nvmlDeviceGetHandleByUUID(args.uuid)
        else:
            handle = nvmlDeviceGetHandleByIndex(args.index)

        if args.test:
            print("Running in test mode - no control commands will be executed")

        name = nvmlDeviceGetName(handle)
        uuid = nvmlDeviceGetUUID(handle)

        print(f"Detected {name} ({uuid})")

        memory_clocks = nvmlDeviceGetSupportedMemoryClocks(handle)
        graphics_clocks = nvmlDeviceGetSupportedGraphicsClocks(handle, max(memory_clocks))

        if args.verbose:
            print(f"Supported core clocks: {graphics_clocks}")

        if args.clock_step == 0:
            step_mhz = get_step_mhz(graphics_clocks)
            if not step_mhz > 0:
                print("Warning: Unable to determine clock step MHz, using fallback value of 15", file=sys.stderr)
                step_mhz = 15
            elif args.verbose:
                print(f"Clock step is {step_mhz} MHz")
        else:
            step_mhz = args.clock_step
            if args.verbose:
                print(f"Using user defined clock step of {step_mhz} MHz")

        if args.curve_increment == 0:
            args.curve_increment = step_mhz * 2

        if not args.curve_increment % step_mhz == 0:
            print(f"Warning: Curve increment should be divisible by clock step ({step_mhz})", file=sys.stderr)

        if args.curve_increment < step_mhz * 2:
            print(f"Error: Curve increment must not be lower than doubled clock step ({step_mhz*2})", file=sys.stderr)
            exit(1)

        try:
            default_persistence_mode = nvmlDeviceGetPersistenceMode(handle)
            if default_persistence_mode:
                print(f"Warning: Persistence mode is already enabled - make sure no other script is controlling clocks", file=sys.stderr)

            if not default_persistence_mode and not args.test:
                nvmlDeviceSetPersistenceMode(handle, NVML_FEATURE_ENABLED)
        except NVMLError as error:
            if error.value == NVML_ERROR_NOT_SUPPORTED:
                print("Warning: Persistence mode is not supported on this device", file=sys.stderr)
            else:
                raise error

        if not args.power_limit == None and args.power_limit > 0:
            min_limit, max_limit = nvmlDeviceGetPowerManagementLimitConstraints(handle)
            min_limit = min_limit / 1000.0
            max_limit = max_limit / 1000.0

            if args.power_limit < min_limit or args.power_limit > max_limit: 
                print(f"Error: Power limit must be in range {min_limit} - {max_limit}", file=sys.stderr)
                exit(1)

        if args.power_limit > 0:
            if args.verbose:
                print(f"Setting power limit to {args.power_limit} W")

            if not args.test:
                nvmlDeviceSetPowerManagementLimit(handle, args.power_limit * 1000)

        if not args.temperature_limit == None and args.temperature_limit > 0:
            min_limit = nvmlDeviceGetTemperatureThreshold(handle, NVML_TEMPERATURE_THRESHOLD_ACOUSTIC_MIN)
            max_limit = nvmlDeviceGetTemperatureThreshold(handle, NVML_TEMPERATURE_THRESHOLD_ACOUSTIC_MAX)

            if args.temperature_limit < min_limit or args.temperature_limit > max_limit: 
                print(f"Error: Temperature limit must be in range {min_limit} - {max_limit}", file=sys.stderr)
                exit(1)

        if args.temperature_limit > 0:
            if args.verbose:
                print(f"Setting temperature limit to {args.temperature_limit} C")

            if not args.test:
                default_temperature_limit = nvmlDeviceGetTemperatureThreshold(handle, NVML_TEMPERATURE_THRESHOLD_ACOUSTIC_CURR)
                nvmlDeviceSetTemperatureThreshold(handle, NVML_TEMPERATURE_THRESHOLD_ACOUSTIC_CURR, args.temperature_limit)

        print(f"Running main loop (sleep = {args.sleep})...")

        state = {'running': True}

        signal.signal(signal.SIGINT, create_interrupt_handler(state))
        signal.signal(signal.SIGTERM, create_interrupt_handler(state))

        min_clock = args.transition_clock
        max_clock = args.target_clock
        offset = args.core_offset

        last_clock = 0
        last_change = time.time()
        last_underclock = False
        underclock = False
        updateclock = True

        while state['running']:
            pstate = nvmlDeviceGetPerformanceState(handle)
            clock = nvmlDeviceGetClockInfo(handle, NVML_CLOCK_GRAPHICS)

            #DEBUG
            #with open('debug-pstate.txt', 'r') as file:
            #    pstate = int(file.read().strip())
            #with open('debug-clock.txt', 'r') as file:
            #    clock = int(file.read().strip())

            if pstate <= args.pstates:
                if not last_underclock and clock >= args.transition_clock - 4 and time.time() - last_change > args.sleep:
                    underclock = True

                    if args.curve:
                        min_clock = args.transition_clock
                        max_clock = args.transition_clock + args.curve_increment

                elif last_underclock and clock <= args.transition_clock + 4 and time.time() - last_change > args.sleep * 2:
                    underclock = False

                if args.curve:
                    if underclock:
                        if clock >= max_clock - 4 and time.time() - last_change > args.sleep:
                            if max_clock + args.curve_increment <= args.target_clock:
                                min_clock = min_clock + args.curve_increment
                                max_clock = max_clock + args.curve_increment

                                if underclock == last_underclock:
                                    updateclock = True

                        elif clock <= min_clock + 4 and time.time() - last_change > args.sleep * 2:
                            if min_clock - args.curve_increment >= args.transition_clock:
                                min_clock = min_clock - args.curve_increment
                                max_clock = max_clock - args.curve_increment

                                if underclock == last_underclock:
                                    updateclock = True

                    if last_clock != clock:
                        offset = interpolate_offset(clock, args.core_offset, args.transition_clock, args.target_clock, step_mhz)
                        updateclock = True

            else:
                underclock = False

            if underclock != last_underclock or updateclock:
                if underclock:
                    if args.verbose:
                        if not updateclock:
                            print(f"Enabling undervolt settings at P{pstate} {clock}")
                        else:
                            print(f"Updating clock lock and offset at P{pstate} {clock}")

                    if args.transition_clock > 0 and args.target_clock > 0:
                        if max_clock > args.target_clock:
                            print(f"Attempted to set max clock to {max_clock} while user defined target clock is {args.target_clock}", file=sys.stderr)
                            max_clock = args.target_clock

                        if not args.test:
                            nvmlDeviceSetGpuLockedClocks(handle, int(min_clock), int(max_clock))

                        if args.verbose:
                            print(f"Locking core clocks at {min_clock} - {max_clock}")

                    if args.core_offset > 0:
                        if offset > args.core_offset:
                            print(f"Attempted to set offset to {offset} while user defined offset is {args.core_offset}", file=sys.stderr)
                            offset = args.core_offset

                        if not args.test:
                            set_pstate_clocks(handle, NVML_CLOCK_GRAPHICS, offset, args.pstates)

                        if args.verbose:
                            print(f"Setting core offset to {offset}")

                    if args.memory_offset > 0 and not updateclock:  # No need to set memory clock each time core clock range is adjusted
                        if not args.test:
                            set_pstate_clocks(handle, NVML_CLOCK_MEM, args.memory_offset, args.pstates)

                        if args.verbose:
                            print(f"Setting memory offset to {args.memory_offset}")
                else:
                    if args.verbose:
                        print(f"Disabling undervolt settings at P{pstate} {clock}")

                    if args.core_offset > 0:
                        if not args.test:
                            set_pstate_clocks(handle, NVML_CLOCK_GRAPHICS, 0, args.pstates)

                        if args.verbose:
                            print(f"Setting core offset to 0")

                    if args.memory_offset > 0:
                        if not args.test:
                            set_pstate_clocks(handle, NVML_CLOCK_MEM, 0, args.pstates)

                        if args.verbose:
                            print(f"Setting memory offset to 0")

                    if args.transition_clock > 0 and args.target_clock > 0:
                        if not args.test:
                            nvmlDeviceSetGpuLockedClocks(handle, 0, args.transition_clock)

                        if args.verbose:
                            print(f"Locking core clocks at 0 - {args.transition_clock}")

                updateclock = False
                last_change = time.time()
                last_underclock = underclock

            last_clock = clock

            time.sleep(args.sleep)
    finally:
        if not args.test:
            nvmlDeviceSetPowerManagementLimit(handle, nvmlDeviceGetPowerManagementDefaultLimit(handle))

            if 'default_temperature_limit' in locals() and not default_temperature_limit == 0:
                nvmlDeviceSetTemperatureThreshold(handle, NVML_TEMPERATURE_THRESHOLD_ACOUSTIC_CURR, default_temperature_limit)

            if args.core_offset > 0:
                set_pstate_clocks(handle, NVML_CLOCK_GRAPHICS, 0, args.pstates)

            if args.memory_offset > 0:
                set_pstate_clocks(handle, NVML_CLOCK_MEM, 0, args.pstates)

            nvmlDeviceResetGpuLockedClocks(handle)

            if 'default_persistence_mode' in locals() and not default_persistence_mode:
                nvmlDeviceSetPersistenceMode(handle, NVML_FEATURE_DISABLED)

        nvmlShutdown()

if __name__ == "__main__":
    main()
