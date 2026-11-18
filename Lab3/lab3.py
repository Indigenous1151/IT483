# Program: IT483 Lab 3
# Author: Nick Kolesar
import threading
import random
import struct
import time
import os
import sys
import hashlib # hashing the checksum
from dataclasses import dataclass
from typing import Optional


VALID_POLICIES = ["every_chunk", "every_n", "time_based", "shutdown_only"]

# validate the program was executed with the proper command line args
if len(sys.argv) < 3:
    print(f"Usage: python3 {sys.argv[0]} <read/write filename> [every_chunk|every_n|time_based|shutdown_only]")
    sys.exit(1)
# check that the policy entered is valid
elif sys.argv[2] not in VALID_POLICIES:
    print(f"ERROR: Invalid policy. Valid policies are: {VALID_POLICIES}")
    sys.exit(1)
else:
    FILENAME = sys.argv[1]
    POLICY   = sys.argv[2]


BUFFER_SIZE = 5
CHUNK_SIZE  = 10
MAX_SIMULATED_STORAGE = 100  # Simulated disk blocks

pending_chunks = []
time_count = time.perf_counter_ns()

# Shared Buffer Structure
shared_buffer = [None] * BUFFER_SIZE
count = 0
head = 0
tail = 0

# Synchronization Primitives (Python Condition encapsulates a lock and condition variables)
condition = threading.Condition()

# Global State managed by OS Simulation
simulated_storage_used = 0
quantization_bits = 32  # Default precision


@dataclass
class Record:
    sequence_num: int
    sample_count: int
    bit_depth: int
    payload: bytes
    checksum: Optional[str] = None

    def compute_checksum(self) -> str:
        """This function computes the checksum from the header and payload as a hex string."""
        hasher = hashlib.sha3_256()
        # Big endian
        # 4 Byte unsigned int for sequence_num
        # 4 Byte unsigned int for sample_count
        # 1 Byte unsigned int for bit_depth
        header_bytes = struct.pack(
            '<IIB', self.sequence_num, self.sample_count, self.bit_depth
        )

        hasher.update(header_bytes)
        hasher.update(self.payload)

        return hasher.hexdigest()


    def is_valid(self) -> bool:
        """This function calculates the checksum and compares against self.checksum"""
        return self.checksum == self.compute_checksum()


    def to_bytes(self) -> bytes:
        """This function converts the record to packed bytes."""
        header_bytes = struct.pack(
            '<IIB', self.sequence_num, self.sample_count, self.bit_depth
        )

        if self.checksum:
            checksum = bytes.fromhex(self.checksum)
            return header_bytes + self.payload + checksum
        else:
            raise Exception("checksum is None")


    def __str__(self):
        return f"{self.sequence_num},{self.sample_count},{self.bit_depth},{self.payload},{self.checksum}"


def sync_file(file_obj) -> int:
    """This function takes any writes in the process' buffers and moves the data
    to disk. Returns time taken in ns."""
    start = time.perf_counter_ns()
    file_obj.flush()
    os.fsync(file_obj.fileno())
    return time.perf_counter_ns() - start


def sync_is_due(policy, pending_chunks, seconds_since_sync,
                every_n=10, interval_seconds=1.0) -> bool:
    """This function determines if the conditions have been met to warrant syncing the file."""
    if policy == "every_chunk":
        return pending_chunks >= 1
    if policy == "every_n":
        return pending_chunks >= every_n
    if policy == "time_based":
        return seconds_since_sync >= interval_seconds
    if policy == "shutdown_only":
        return False
    # I added a check on the valid policies, but I'll keep this here
    raise ValueError(f"Unknown policy: {policy}")


def encode_chunk(samples, bits) -> bytes:
    """Encode normalized float samples (-1.0 to 1.0) at the selected bit depth."""
    samples = [max(-1.0, min(1.0, float(x))) for x in samples]

    if not samples:
        return b""

    if bits == 32:
        # Four bytes per sample: floating-point storage, no integer quantization.
        return struct.pack(f"<{len(samples)}f", *samples)

    if bits == 16:
        values = [round(x * 32767) for x in samples]
        return struct.pack(f"<{len(values)}h", *values)

    if bits == 8:
        values = [round(x * 127) for x in samples]
        return struct.pack(f"<{len(values)}b", *values)

    raise ValueError("bits must be 32, 16, or 8")


def producer_mic():
    global count, tail, simulated_storage_used

    rng = random.Random(999)
    # Generate mock 32-bit float audio samples in a chunk
    chunk_num = 0

    while True:
        with condition:
            while count == BUFFER_SIZE:
                condition.wait()

            chunk = [rng.random() for _ in range(CHUNK_SIZE)]

            shared_buffer[tail] = (chunk_num, chunk) # type: ignore
            tail = (tail + 1) % BUFFER_SIZE
            count += 1

            condition.notify()

        time.sleep(0.05)  # Simulate audio sampling rate interval


def consumer_storage():
    global count, head, simulated_storage_used, quantization_bits, time_count
    with open("storage.txt", "wb") as file:
        while simulated_storage_used < MAX_SIMULATED_STORAGE:
            with condition:
                while count == 0 and simulated_storage_used < MAX_SIMULATED_STORAGE:
                    condition.wait()

                if count == 0 and simulated_storage_used >= MAX_SIMULATED_STORAGE:
                    break

                # Fetch sample from buffer
                if shared_buffer[head] != None:
                    sequence_num, raw_chunk = shared_buffer[head] # type: ignore
                else:
                    print("shared_buffer read None")
                    break

                head = (head + 1) % BUFFER_SIZE
                count -= 1

                # determine the quantization bits
                if simulated_storage_used >= 80:
                    quantization_bits = 8
                elif simulated_storage_used >= 50:
                    quantization_bits = 16
                else:
                    quantization_bits = 32

                # convert to 32 bit float if 32, otherwise make into integer
                chunk = encode_chunk(raw_chunk, quantization_bits)

                # create the new record
                record = Record(
                    sequence_num=sequence_num,
                    sample_count=len(raw_chunk),
                    bit_depth=quantization_bits,
                    payload=chunk
                )
                # update the checksum for the created Record
                record.checksum = record.compute_checksum()

                # write record to file
                file.write(record.to_bytes())

                pending_chunks.append(record)

                seconds_since_sync = (time.perf_counter_ns() - time_count) / 1_000_000_000
                # after sample has been created, now we determine if file sync needed
                if sync_is_due(POLICY, pending_chunks, seconds_since_sync):
                    sync_file(file)
                    pending_chunks.clear()
                    time_count = time.perf_counter_ns() # update when the last sync happened

                # maintaining the default concept of 1 being 2 bytes
                simulated_storage_used += (quantization_bits / 16) * CHUNK_SIZE
                print(f"Stored record. Record: {record}. "
                      f"Storage: {simulated_storage_used}/{MAX_SIMULATED_STORAGE}")

                # -------------------------

                condition.notify()

            time.sleep(0.08)  # Simulate storage I/O delay


# TODO: finish this function
def validate_contents(filename):
    "Reads the records in the byte file and truncates invalid record"
    recovered_records = []
    last_valid_position = 0
    if os.path.isfile("./"+filename):
        with open(filename, "rb+") as file:
            pass

    return recovered_records


if __name__ == "__main__":
    records = validate_contents(FILENAME)

    if records != []:
        # show what records were read from the file
        print(f"Contents of {FILENAME}")
        print("sequence_num,sample_count,bit_depth,payload_checksum")
        for record in records:
            print(record)
    else:
        print(f"No file named {FILENAME} exists.")

    print("\n-----------------------\n")

    prod_thread = threading.Thread(target=producer_mic)
    cons_thread = threading.Thread(target=consumer_storage)

    prod_thread.start()
    cons_thread.start()

    prod_thread.join()
    cons_thread.join()

    print("Storage Full Simulation Finished.")