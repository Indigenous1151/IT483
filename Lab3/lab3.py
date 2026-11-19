# Program: IT483 Lab 3
# Author: Nick Kolesar
import threading
import random
import struct
import queue
import time
import os
import sys
import hashlib # hashing the checksum
from dataclasses import dataclass
from typing import Optional


VALID_POLICIES = ["every_chunk", "every_n", "time_based", "shutdown_only"]

# validate the program was executed with the proper command line args
if len(sys.argv) < 2:
    print(f"Usage: python3 {sys.argv[0]} [every_chunk|every_n|time_based|shutdown_only]")
    sys.exit(1)
# check that the policy entered is valid
elif sys.argv[1] not in VALID_POLICIES:
    print(f"ERROR: Invalid policy. Valid policies are: {VALID_POLICIES}")
    sys.exit(1)
else:
    POLICY   = sys.argv[1]
    FILENAME = f"audio_{POLICY}.bin" # saving as binary file


BUFFER_SIZE = 5
CHUNK_SIZE  = 10
MAX_STORAGE_BYTES = 1024 # storing 1KB of data

def storage_percent(used, max_bytes):
    """This function calculates the percentage of storage used"""
    return (used / max_bytes) * 100 if max_bytes > 0 else 0

pending_chunks = []
time_count = time.perf_counter_ns()

audio_queue = queue.Queue(maxsize=BUFFER_SIZE)
stop_event = threading.Event()

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


@dataclass
class Stats:
    policy: str
    recovered_chunks: int = 0
    chunks_written: int = 0
    sync_count: int = 0
    total_sync_ns: int = 0
    file_size_bytes: int = 0
    start_ns: int = 0
    end_ns: int = 0
    
    def record_sync(self, sync_ns: int):
        self.sync_count += 1
        self.total_sync_ns += sync_ns
        
    @property
    def total_sync_ms(self) -> float:
        return self.total_sync_ns / 1_000_000
    
    @property
    def avg_sync_ms(self) -> float:
        if self.sync_count == 0:
            return 0.0
        return self.total_sync_ms / self.sync_count
    
    @property
    def recording_seconds(self) -> float:
        return (self.end_ns - self.start_ns) / 1_000_000_000
    
    @property
    def chunks_per_second(self) -> float:
        return self.chunks_written / self.recording_seconds if self.recording_seconds > 0 else 0.0
    
    def summary(self):
        return (
            f"Policy: {self.policy}\n"
            f"Recovered Chunks (prior run): {self.recovered_chunks}\n"
            f"Chunks Written:               {self.chunks_written}\n"
            f"Sync Count:                   {self.sync_count}\n"
            f"Total Sync Time (ms):         {self.total_sync_ms:.3f}\n"
            f"Average Sync Time (ms):       {self.avg_sync_ms:.3f}\n"
            f"Recording Duration (s):       {self.recording_seconds:.3f}\n"
            f"Chunks per Second:            {self.chunks_per_second:.3f}\n"
            f"File Size (bytes):            {self.file_size_bytes}\n"
        )

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
    rng = random.Random(999)
    # Generate mock 32-bit float audio samples in a chunk
    chunk_num = 0

    while not stop_event.is_set():
        chunk = [rng.uniform(-1.0, 1.0) for _ in range(CHUNK_SIZE)]
        try:
            audio_queue.put((chunk_num, chunk), timeout=0.05)
            chunk_num += 1
        except queue.Full:
            pass

        time.sleep(0.05)  # Simulate audio sampling rate interval


def consumer_storage():
    global simulated_storage_used, quantization_bits, time_count
    with open(FILENAME, "wb") as file:
        while simulated_storage_used < MAX_STORAGE_BYTES and not stop_event.is_set():
            try:
                sequence_num, raw_chunk = audio_queue.get(timeout=0.05)
            except queue.Empty:
                continue

            try:
                percent_used = storage_percent(simulated_storage_used, MAX_STORAGE_BYTES)
                # determine the quantization bits
                if percent_used >= 80:
                    quantization_bits = 8
                elif percent_used >= 50:
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
                encoded_bytes = record.to_bytes()
                # prevent writing if it exceeds max storage bytes
                if simulated_storage_used + len(encoded_bytes) > MAX_STORAGE_BYTES:
                    break

                # write record to file
                file.write(record.to_bytes())
                stats.chunks_written += 1
                pending_chunks.append(record)

                seconds_since_sync = (time.perf_counter_ns() - time_count) / 1_000_000_000
                # after sample has been created, now we determine if file sync needed
                if sync_is_due(POLICY, len(pending_chunks), seconds_since_sync):
                    stats.record_sync(sync_file(file))
                    pending_chunks.clear()
                    time_count = time.perf_counter_ns() # update when the last sync happened

                # maintaining the default concept of 1 being 2 bytes
                simulated_storage_used += len(encoded_bytes)
                print(f"Stored record. Record: {record}. "
                      f"Storage: {simulated_storage_used}/{MAX_STORAGE_BYTES}", flush=True)

                # -------------------------

            finally:
                audio_queue.task_done()

            time.sleep(0.08)  # Simulate storage I/O delay

        stop_event.set() # signal producer to stop

        # empty the queue
        while not audio_queue.empty():
            try:
                audio_queue.get_nowait()
                audio_queue.task_done()
            except queue.Empty:
                break
        stats.record_sync(sync_file(file))  # final sync before closing


def validate_contents(filename):
    "Reads the records in the byte file and truncates invalid record"
    global time_count
    recovered_records = []
    last_valid_position = 0
    if os.path.isfile("./"+filename):
        with open(filename, "rb+") as file:
            while True:
                record_start = file.tell()

                # read the 9 byte header
                header = file.read(9)

                # check if at the end of file
                if not header:
                    break

                # incomplete header
                if len(header) != 9:
                    break

                sequence_num, sample_count, bit_depth = struct.unpack(
                    '<IIB', header
                )

                # validate the header
                if bit_depth not in (8, 16, 32):
                    break

                if sample_count == 0 or sample_count > 10:
                    break

                payload_size = sample_count * (bit_depth // 8)

                payload = file.read(payload_size)

                # incomplete payload
                if len(payload) != payload_size:
                    break

                checksum = file.read(32)

                # incomplete checksum
                if len(checksum) != 32:
                    break

                # build record
                record = Record(
                    sequence_num=sequence_num,
                    sample_count=sample_count,
                    bit_depth=bit_depth,
                    payload=payload,
                    checksum=checksum.hex()
                )

                # validate checksum
                if not record.is_valid():
                    break

                recovered_records.append(record)

                last_valid_position = file.tell()

            # remove invalid remainder of file
            file.truncate(last_valid_position)
            stats.record_sync(sync_file(file))
            time_count = time.perf_counter_ns()

    print(f"Recovered {len(recovered_records)} from {FILENAME}")

    return recovered_records


if __name__ == "__main__":
    stats = Stats(policy=POLICY)
    records = validate_contents(FILENAME)

    if records != []:
        # show what records were read from the file
        print(f"Contents of {FILENAME}")
        print("sequence_num,sample_count,bit_depth,payload,checksum")
        for record in records:
            print(record)
    else:
        print(f"No file named {FILENAME} exists.")

    print("\n-----------------------\n")

    prod_thread = threading.Thread(target=producer_mic)
    cons_thread = threading.Thread(target=consumer_storage)

    # save current time
    time_count = time.perf_counter_ns()
    
    stats.recovered_chunks = len(records)
    stats.start_ns = time_count

    prod_thread.start()
    cons_thread.start()

    prod_thread.join()
    cons_thread.join()
    
    stats.end_ns = time.perf_counter_ns()
    stats.file_size_bytes = os.path.getsize(FILENAME) if os.path.isfile(FILENAME) else 0
    
    print("\nSimulation Summary:")
    print(stats.summary())

    print("\nStorage Full Simulation Finished.")