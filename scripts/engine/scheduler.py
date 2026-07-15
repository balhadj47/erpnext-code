"""Phase 11.6: Parallel Scheduler

Executes independent tasks concurrently while respecting the dependency graph.
Tasks with no dependencies on each other can run in parallel.
"""

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Callable

from .interfaces import Task, TaskResult, TaskStatus


@dataclass
class ScheduleGroup:
    """A group of tasks that can run in parallel."""
    tasks: list[Task]
    level: int  # dependency depth


class ParallelScheduler:
    """Schedules tasks in parallel waves based on dependency graph."""

    def __init__(self, max_workers: int = 4):
        self.max_workers = max_workers

    def schedule(self, tasks: list[Task]) -> list[ScheduleGroup]:
        """Partition tasks into parallel execution groups.

        Tasks in the same group have no dependencies on each other
        and all their dependencies are in earlier groups.
        """
        if not tasks:
            return []

        task_map = {t.id: t for t in tasks}
        groups: list[ScheduleGroup] = []
        completed: set[str] = set()
        remaining = set(task_map.keys())

        level = 0
        while remaining:
            group_tasks = []
            for tid in sorted(remaining):
                task = task_map[tid]
                deps_met = all(
                    dep in completed or dep not in task_map  # dep outside our set or completed
                    for dep in task.depends_on
                )
                if deps_met:
                    # Check no dependency within this same group
                    deps_in_remaining = set(task.depends_on) & remaining
                    if not deps_in_remaining:
                        group_tasks.append(task)

            if not group_tasks:
                # Circular or unresolvable — add remaining sequentially
                for tid in sorted(remaining):
                    group_tasks.append(task_map[tid])
                groups.append(ScheduleGroup(tasks=group_tasks, level=level))
                break

            for t in group_tasks:
                remaining.discard(t.id)

            groups.append(ScheduleGroup(tasks=group_tasks, level=level))
            completed.update(t.id for t in group_tasks)
            level += 1

        return groups

    def execute_group(
        self,
        group: ScheduleGroup,
        executor_fn: Callable[[Task], TaskResult],
    ) -> list[TaskResult]:
        """Execute a group of tasks in parallel."""
        if len(group.tasks) == 1:
            return [executor_fn(group.tasks[0])]

        results: list[TaskResult] = []
        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(group.tasks))) as executor:
            futures = {
                executor.submit(executor_fn, task): task
                for task in group.tasks
            }
            for future in as_completed(futures):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    task = futures[future]
                    results.append(TaskResult(
                        task_id=task.id,
                        status=TaskStatus.FAILED,
                        error=str(e),
                    ))
        return results

    def get_parallelism_report(self, groups: list[ScheduleGroup]) -> dict:
        """Generate a report on parallel execution opportunities."""
        sequential = sum(1 for g in groups if len(g.tasks) == 1)
        parallel = sum(1 for g in groups if len(g.tasks) > 1)
        total_tasks = sum(len(g.tasks) for g in groups)
        max_parallel = max((len(g.tasks) for g in groups), default=0)

        return {
            "total_groups": len(groups),
            "sequential_groups": sequential,
            "parallel_groups": parallel,
            "total_tasks": total_tasks,
            "max_parallelism": max_parallel,
            "estimated_speedup": f"{total_tasks / len(groups):.1f}x" if groups else "1x",
        }
