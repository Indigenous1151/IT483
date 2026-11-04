import os
import time

def sync_file(file_obj):
    start = time.perf_counter_ns()
    file_obj.flush()
    os.fsync(file_obj.fileno())
    return time.perf_counter_ns() - start

def sync_is_due(policy, pending_chunks, seconds_since_sync,
                every_n=10, interval_seconds=1.0):
    if policy == "every_chunk":
        return pending_chunks >= 1
    if policy == "every_n":
        return pending_chunks >= every_n
    if policy == "time_based":
        return seconds_since_sync >= interval_seconds
    if policy == "shutdown_only":
        return False
    raise ValueError(f"Unknown policy: {policy}")