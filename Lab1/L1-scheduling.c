#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>

#define MAX_PROCESSES 4

typedef struct {
    int pid;
    int arrival_time;
    int burst_time;
    int remaining_time;
    bool is_io_bound;
    int completion_time;
    int turnaround_time;
    int waiting_time;
    bool is_completed;
} Process;

void init_processes(Process proc[]) {
    // Process 1: Heavy AI Inference
    proc[0] = (Process){1, 0, 10, 10, false, 0, 0, 0, false};
    // Process 2: Camera Frame Stream
    proc[1] = (Process){2, 1, 2, 2, true, 0, 0, 0, false};
    // Process 3: Audio Input Packet
    proc[2] = (Process){3, 2, 1, 1, true, 0, 0, 0, false};
    // Process 4: LLM Token Generation
    proc[3] = (Process){4, 3, 8, 8, false, 0, 0, 0, false};
}

void simulate_scheduler(const char* policy) {
    Process proc[MAX_PROCESSES];
    init_processes(proc);

    int current_time = 0;
    int completed = 0;

    printf("\n--- Running Scheduler Simulation: %s ---\n", policy);

    while (completed < MAX_PROCESSES) {
        int selected_idx = -1;

        /* 
         * STUDENT TASK: Implement the scheduling selection logic here.
         * Find a process that has arrived (proc[i].arrival_time <= current_time)
         * and is not yet completed (!proc[i].is_completed).
         * 
         * - If policy is "FCFS": Select the arrived process with the smallest arrival_time.
         * - If policy is "SJF": Select the arrived process with the shortest remaining_time.
         */
        
        // --- STUDENT CODE HERE ---

        // -------------------------

        // If no process has arrived yet, advance time (CPU Idle)
        if (selected_idx == -1) {
            current_time++;
            continue;
        }

        // Execute the chosen process to completion (Non-preemptive simulation)
        Process* p = &proc[selected_idx];
        printf("[Time %2d]: Running P%d (%s) for %d units.\n", 
               current_time, p->pid, p->is_io_bound ? "I/O-Bound" : "AI Inference", p->remaining_time);

        current_time += p->remaining_time;
        p->remaining_time = 0;
        p->is_completed = true;
        completed++;

        // Calculate performance metrics
        p->completion_time = current_time;
        p->turnaround_time = p->completion_time - p->arrival_time;
        p->waiting_time = p->turnaround_time - p->burst_time;
    }

    // Print out aggregate evaluation statistics
    float total_turnaround = 0, total_waiting = 0;
    for (int i = 0; i < MAX_PROCESSES; i++) {
        total_turnaround += proc[i].turnaround_time;
        total_waiting += proc[i].waiting_time;
    }

    printf("\n>> Evaluation Metrics for %s:\n", policy);
    printf("   Average Turnaround Time: %.2f time units\n", total_turnaround / MAX_PROCESSES);
    printf("   Average Waiting Time:    %.2f time units\n", total_waiting / MAX_PROCESSES);
}

int main() {
    simulate_scheduler("FCFS");
    // Once implemented, students can uncomment this to compare:
    // simulate_scheduler("SJF");
    return 0;
}
