# Author: Nick Kolesar

import threading

import queue

import time

import random

 

# Simulation Setup

MATRIX_ROWS = 1000

VECTOR_SIZE = 50

NUM_THREADS = 4

USE_STATIC = True

 

# Generate a mock pruned matrix (50% zeros) and an input vector

matrix = [[random.choice([0.0, random.random()]) for _ in range(VECTOR_SIZE)] for _ in range(MATRIX_ROWS)]

vector = [random.random() for _ in range(VECTOR_SIZE)]

output = [0.0] * MATRIX_ROWS

 

# Thread-safe queue to hold row indices for dynamic scheduling
if not USE_STATIC:
    row_queue = queue.Queue()

    for i in range(MATRIX_ROWS):

        row_queue.put(i)
else:
    row_queue = None

# Lock to protect printing or shared output modification if needed

output_lock = threading.Lock()

 

def worker(thread_id, static=False):

    """

    STUDENT TASK: Complete this worker function.

    Pull a row index from row_queue until it is empty.
    Loop through the items in that row.
    Optimization: Skip the multiplication if the matrix weight is 0 (Pruning).
    Accumulate the dot product and save it to the global 'output' list.

    """

    print(f"Thread-{thread_id} started.")
    if USE_STATIC:
        num_threads_with_extra_row = MATRIX_ROWS % NUM_THREADS
        num_rows_to_complete = MATRIX_ROWS // NUM_THREADS + (1 if thread_id < num_threads_with_extra_row else 0)
        # figure out what row worker starts at, accounting for uneven distributions as well
        cur_row = MATRIX_ROWS // NUM_THREADS * thread_id + (thread_id if thread_id < num_threads_with_extra_row else num_threads_with_extra_row)
    else:
        num_rows_to_complete = 0
        cur_row = 0

    while USE_STATIC and num_rows_to_complete > 0 or not USE_STATIC and not row_queue.empty():

        try:

            # Non-blocking get in case another thread empties it concurrently
            with output_lock:
                if USE_STATIC:
                    row_idx = cur_row
                    cur_row += 1
                else:
                    row_idx = row_queue.get_nowait()
                num_rows_to_complete -= 1

        except queue.Empty:

            break

        dot_product = 0.0

        # --- STUDENT CODE HERE ---
        print(f"worker {thread_id} running row {row_idx}")
        # Hint: Multiply matrix[row_idx][j] * vector[j]
        for j in range(VECTOR_SIZE):
        # Skip if matrix[row_idx][j] == 0
            if matrix[row_idx][j] == 0:
                continue
            dot_product += matrix[row_idx][j] * vector[j]

        

        # -------------------------

        output[row_idx] = dot_product

        # row_queue is None for static scheduling
        if row_queue:
            row_queue.task_done()

 

# Spawning threads

threads = []

for t in range(NUM_THREADS):

    thread = threading.Thread(target=worker, args=(t, USE_STATIC))

    threads.append(thread)

    thread.start()

 

# Wait for all threads to finish

for thread in threads:

    thread.join()


print("Matrix multiplication complete. Output validated.")