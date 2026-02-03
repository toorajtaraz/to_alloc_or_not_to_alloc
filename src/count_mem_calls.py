import subprocess
import resource
import time
import datetime
import sys
import os
from collections import Counter
import argparse


def validate_binary(args):
    binary = args.file or args.command
    if not binary:
        raise argparse.ArgumentTypeError(
            "you must provide either --file or --command"
        )
    if args.file:
        if not (os.path.isfile(binary) and os.access(binary, os.X_OK)):
            raise argparse.ArgumentTypeError(
                f"{binary} is not an executable file"
            )
    return binary


def handle_time(args):
    so_path = os.path.join(args.ldpreload, args.allocator_replacement)
    if args.allocator_replacement != "gnu":
        if not os.path.isfile(so_path):
            sys.exit("invalid ldpreload path or allocator shared object")
    return {
        "mode": "time",
        "binary": validate_binary(args),
        "iters": args.iters,
        "ld_preload": args.ldpreload,
        "allocator": args.allocator_replacement,
        "so_path": so_path,
    }


def handle_strace(args):
    return {
        "mode": "strace",
        "binary": validate_binary(args),
    }


def setup_argparse():
    parser = argparse.ArgumentParser(
        description="A simple program that counts syscalls!"
    )

    parser.add_argument("--file", "-f", type=str)
    parser.add_argument("--command", "-c", type=str)

    subparsers = parser.add_subparsers(dest="mode", required=True)

    time_parser = subparsers.add_parser("time")
    time_parser.add_argument("--iters", "-i", type=int, default=25)
    time_parser.add_argument("--ldpreload", required=True)
    time_parser.add_argument(
        "--allocator-replacement",
        choices={"libmimalloc.so", "gnu"},
        default="gnu",
    )
    time_parser.set_defaults(func=handle_time)

    strace_parser = subparsers.add_parser("strace")
    strace_parser.set_defaults(func=handle_strace)

    args = parser.parse_args()
    return args.func(args)


config = setup_argparse()


now = datetime.datetime.now()
today_date = now.strftime("%Y_%m_%d_%H_%M_%S")
output_log = f"strace_counter_{today_date}"

command = ""
if config['mode'] == "time":
    mode = "time"
    command = []
else:
    command = ["strace", "-f", "-o", output_log]
command.extend(config['binary'].split(" "))


if config['mode'] == "strace":
    try:
        res = subprocess.run(command, check=True, stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, text=True)
    except subprocess.CalledProcessError as e:
        print(f"App failed: {e}")

    syscall_list = []

    with open(output_log, 'r') as f:
        for line in f:
            try:
                token = line.split(" ")[1].split("(")[0]
                if token[0].isalnum():
                    syscall_list.append(token)
            except IndexError:
                continue
    os.remove(output_log)

    syscall_hist = dict(Counter(syscall_list))

    print(syscall_hist)
elif config['mode'] == "time":
    def parse_time(time_taken_str):
        real_time = -1
        user_time = -1
        system_time = -1

        real_time = time_taken_str.split("Real time: ")[
            1].split(",")[0].strip()
        user_time = time_taken_str.split("User time: ")[
            1].split(",")[0].strip()
        system_time = time_taken_str.split("System time: ")[
            1].split(",")[0].strip()

        def parse_lengthy_time(t):
            m, s = t.split(":")
            return int(m) * 60 + float(s)
        if ":" in real_time:
            real_time = parse_lengthy_time(real_time)
        else:
            real_time = float(real_time)

        if ":" in user_time:
            user_time = parse_lengthy_time(user_time)
        else:
            user_time = float(user_time)

        if ":" in system_time:
            system_time = parse_lengthy_time(system_time)
        else:
            system_time = float(system_time)

        return real_time, user_time, system_time

    alloc_real_times = []

    alloc_user_times = []

    alloc_system_times = []

    env = os.environ.copy()

    if config['allocator'] != "gnu":
        env['LD_PRELOAD'] = config['so_path']
    for _ in range(config['iters']):
        try:
            ru0 = resource.getrusage(resource.RUSAGE_CHILDREN)
            t0 = time.perf_counter()
            subprocess.run(command, check=True, stdout=subprocess.DEVNULL, env=env,
                           stderr=subprocess.DEVNULL, text=True)

            t1 = time.perf_counter()
            ru1 = resource.getrusage(resource.RUSAGE_CHILDREN)
            r = t1 - t0
            u = ru1.ru_utime - ru0.ru_utime
            s = ru1.ru_stime - ru0.ru_stime

            alloc_real_times.append(r)
            alloc_user_times.append(u)
            alloc_system_times.append(s)
        except subprocess.CalledProcessError as e:
            print(f"App failed: {e}")
            exit(-1)

    print(sum(alloc_real_times))

    print(sum(alloc_user_times))

    print(sum(alloc_system_times))
