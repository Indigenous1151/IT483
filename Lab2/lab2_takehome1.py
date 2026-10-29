# Lab 2 take home
# Author: Nick Kolesar
# Date: 10/27/2026
import threading
import random
import time
import numpy as np

BUFFER_SIZE = 5
MAX_SIMULATED_STORAGE = 100  # Simulated disk blocks

# Shared Buffer Structure
shared_buffer = [0.0] * BUFFER_SIZE
count = 0
head = 0
tail = 0

# Synchronization Primitives (Python Condition encapsulates a lock and condition variables)
condition = threading.Condition()

# Global State managed by OS Simulation
simulated_storage_used = 0
quantization_bits = 32  # Default precision

def producer_mic():
    global count, tail, simulated_storage_used

    while simulated_storage_used < MAX_SIMULATED_STORAGE:
        with condition:
            while count == BUFFER_SIZE:
                condition.wait()

            # Generate a mock 32-bit float audio sample
            sample = random.random()

            shared_buffer[tail] = sample
            tail = (tail + 1) % BUFFER_SIZE
            count += 1

            condition.notify()
        
        time.sleep(0.05)  # Simulate audio sampling rate interval

def consumer_storage():
    global count, head, simulated_storage_used, quantization_bits
    with open("storage.txt", "w") as file:
        while simulated_storage_used < MAX_SIMULATED_STORAGE:
            with condition:
                while count == 0 and simulated_storage_used < MAX_SIMULATED_STORAGE:
                    condition.wait()

                if count == 0 and simulated_storage_used >= MAX_SIMULATED_STORAGE:
                    break

                # Fetch sample from buffer
                raw_sample = shared_buffer[head]
                head = (head + 1) % BUFFER_SIZE
                count -= 1

                # I moved this notify because the quantization doesn't
                # actually need to be in the critical section
                condition.notify()

            # 

            # determine the quantization bits
            if simulated_storage_used >= 80:
                quantization_bits = 8
            elif simulated_storage_used >= 50:
                quantization_bits = 16
            else:
                quantization_bits = 32

            # convert to 32 bit float if 32, otherwise make into integer
            if quantization_bits == 32:
                sample = np.float32(raw_sample)
            else:
                scale = 2 ** quantization_bits - 1
                sample = max(0, min(scale, round(raw_sample * scale)))

            # write the quantized sample to storage.txt
            file.write(str(sample) + "\n")
            # maintaining the default concept of 1 being 2 bytes
            simulated_storage_used += (quantization_bits / 16)
            print(f"Stored sample. Bits: {quantization_bits}. Storage: {simulated_storage_used}/{MAX_SIMULATED_STORAGE}")

                # -------------------------


            time.sleep(0.08)  # Simulate storage I/O delay


if __name__ == "__main__":
    prod_thread = threading.Thread(target=producer_mic)
    cons_thread = threading.Thread(target=consumer_storage)

    prod_thread.start()
    cons_thread.start()

    prod_thread.join()
    cons_thread.join()

    print("Storage Full Simulation Finished.")