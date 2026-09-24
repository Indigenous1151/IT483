// Author: Nick Kolesar
// Class: IT483
// Date: 9/16/2026
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <string.h>
#include <math.h>

#define MAX_PROCESSES 4

// Extra definitions and a constant for error output
const char* VALID_POLICIES[] = {"FCFS", "SJF", "RR"};
#define NUM_VALID_POLICIES 3
#define TIME_QUANTUM 4
#define GREEN "\033[0;32m"
#define BLUE  "\033[0;34m"
#define RESET "\033[0m"

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

// Linked list node
typedef struct Node {
    int pid;
    int time_added; // need to track waiting time
    struct Node* next;
} Node;

// Linked list queue
typedef struct {
    Node* front;
    Node* back;
    int size;
} ReadyQueue;

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

void push(ReadyQueue *self, int value, int time) {
    // allocate new node for list
    Node *new_node = malloc(sizeof(Node));
    new_node->pid = value;
    new_node->time_added = time;
    new_node->next = NULL;

    if (self->size == 0)
    {
        self->front = new_node;
        self->back = new_node;
    }
    else {
        // attach new node to the back of the list
        self->back->next = new_node;
        // move the back pointer to the new back of the list
        self->back = self->back->next;
    }
    // update the size of the queue
    self->size += 1;
}

Node *pop(ReadyQueue *self) {
    if (self->front != NULL) {
        Node* front_node = self->front;

        // move front to next code in queue
        self->front = self->front->next;

        // reduce the size of the queue by 1
        self->size -= 1;

        // empty queue after pop, so update back to be null
        if (self->size == 0) {
            self->back = NULL;
        }

        // return the front node
        return front_node;
    }
    // pid cannot be negative, so -1 shows error
    else {
        return NULL;
    }
}

// implemented just in case
Node* peek (ReadyQueue *self) {
    return (self != NULL) ? self->front : NULL;
}

// returns size of self or -1 if self is NULL
int size(ReadyQueue *self) {
    return (self != NULL) ? self->size : -1;
}

// iterate through the queue, and return true if target node is found
bool find(ReadyQueue *self, int target) {
    Node *iter = self->front;

    while (iter != NULL) {
        if (iter->pid == target)
            return true;
        iter = iter->next;
    }
    return false;
}

void simulate_scheduler(const char* policy) {
    Process proc[MAX_PROCESSES];
    init_processes(proc);
    ReadyQueue ready_queue = {NULL, NULL, 0}; // custom linked list
    int current_time = 0;
    int completed = 0;
    bool rr_seen[MAX_PROCESSES] = {false};

    printf("\n--- Running Scheduler Simulation: %s ---\n", policy);

    while (completed < MAX_PROCESSES) {
        int selected_idx = -1;

        /*
         * STUDENT TASK: Implement the scheduling selection logic here.
         * Find a process that has arrived (proc[i].arrival_time <= current_time)
         * and is not yet completed (!proc[i].is_completed).
         *
         * - If policy is "FCFS": Select the arrived process with the smallest arrival_time.
         * - If policy is "SJF":  Select the arrived process with the shortest remaining_time.
         * - If policy is "RR":   Each process takes equal amount of time determined by a time quant.
         */

        // --- STUDENT CODE HERE ---
        int rr_pushed_time = -1;
        static int previous_idx = -1;

        if (strcmp(policy, "FCFS") == 0)
        {
            int first_arrived = -1; // -1 means no process
            for (int i = 0; i < MAX_PROCESSES; i++)
            {
                // skip check if the process hasn't arrived yet
                if (current_time < proc[i].arrival_time || proc[i].is_completed)
                    continue;
                // nobody is scheduled yet, so job i is candidate
                if (first_arrived == -1)
                    first_arrived = i;
                else if (proc[first_arrived].arrival_time > proc[i].arrival_time)
                    first_arrived = i;
            }

            selected_idx = first_arrived;
        }
        else if (strcmp(policy, "SJF") == 0)
        {
            int shortest_job = -1; // -1 means no process
            for (int i = 0; i < MAX_PROCESSES; i++)
            {
                // skip check if the process hasn't arrived yet
                if (current_time < proc[i].arrival_time || proc[i].is_completed)
                    continue;
                // nobody is scheduled yet, so job i is candidate
                if (shortest_job == -1)
                    shortest_job = i;
                else if (proc[shortest_job].remaining_time > proc[i].remaining_time)
                    shortest_job = i;
            }

            selected_idx = shortest_job;
        }
        else if (strcmp(policy, "RR") == 0)
        {
            int rr_job = -1; // start with nobody

            for (int count = 0; count < MAX_PROCESSES; count++)
            {
                int next_idx = -1;

                // run through each process and find min unseen arrival time to push
                for (int i = 0; i < MAX_PROCESSES; i++)
                {
                    if (rr_seen[i] || proc[i].is_completed || i == previous_idx || current_time < proc[i].arrival_time)
                        continue;

                    if (next_idx == -1 || proc[i].arrival_time < proc[next_idx].arrival_time)
                        next_idx = i;
                }

                if (next_idx == -1)
                    break;

                push(&ready_queue, proc[next_idx].pid, proc[next_idx].arrival_time);

                rr_seen[next_idx] = true;
            }

            // readd the previous job if there was one
            if (previous_idx != -1 && !proc[previous_idx].is_completed)
                push(&ready_queue, proc[previous_idx].pid, current_time);

            // pop node from the queue to decide on the id
            Node *popped_node = pop(&ready_queue);

            if (popped_node == NULL)
                rr_job = -1;
            else {
                // store when it was pushed to the queue and its pid
                rr_pushed_time = popped_node->time_added;
                rr_job = popped_node->pid - 1;

                // delete the node
                free(popped_node);
                popped_node = NULL;
            }

            selected_idx = rr_job;
            previous_idx = selected_idx;
        }
        else
        {
            printf("Invalid policy provided: %s\n", policy);
            printf("Allowed Policies:\n");
            for (int i = 0; i < NUM_VALID_POLICIES; i++)
            {
                printf("\t%s%s%s\n",GREEN, VALID_POLICIES[i], RESET);
            }
            exit(1);
        }

        // -------------------------

        // If no process has arrived yet, advance time (CPU Idle)
        if (selected_idx == -1) {
            current_time++;
            continue;
        }

        Process* p = &proc[selected_idx];

        if (strcmp(policy, "RR") == 0) {
            int burst = fmin(p->remaining_time, TIME_QUANTUM);
            printf("[Time %2d]: Running P%d (%s) for %d units.\n",
                    current_time, p->pid, p->is_io_bound ? "I/O-Bound" : "AI Inference", burst);
            // update the waiting time before updating current time to prevent counting the execution
            p->waiting_time += current_time - rr_pushed_time;

            // update current time based on either quantum or remaining time (whichever is smaller)
            current_time += burst;
            p->remaining_time -= burst;

            if (p->remaining_time == 0) {
                p->is_completed = true;
                completed++;

                // update completion and turnaround times
                p->completion_time = current_time;
                p->turnaround_time = current_time - p->arrival_time; // doesn't really matter
            }
        }
        else {
            // Execute the chosen process to completion (Non-preemptive simulation)
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
    simulate_scheduler("SJF");
    simulate_scheduler("RR");
    return 0;
}
