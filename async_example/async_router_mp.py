#!/usr/bin/env python3
# -*- mode: python; python-indent: 4 -*-

# This is an async example starting 10000 instances of async_router in
# 10 separate processes with 1000 each.


from multiprocessing import Process
import async_router


def main():
    total = 10000
    parallel = 10
    start_port = 30000
    perproc = total//parallel

    processes = []
    for i in range(0, parallel):
        process = Process(target=async_router.main_servers, args=(perproc, start_port))
        process.start()
        processes.append(process)
        start_port += perproc

    [ p.join() for p in processes ]

if __name__ == '__main__':
    main()
