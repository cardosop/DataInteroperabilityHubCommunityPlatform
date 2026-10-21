# Workflow DSL Documentation

## Overview

The Workflow DSL (Domain-Specific Language) is used to define workflows in JSON or YAML format. Workflows consist of a series of steps that are executed sequentially or in parallel.

## Workflow Structure

A workflow definition has the following structure:

```json
{
  "version": "1.0.0",
  "dependencies": ["workflow1", "workflow2"],
  "steps": [
    {
      "name": "step1",
      "type": "task",
      "task": "task_name",
      "input": {}
    }
  ],
  "compensation": {
    "enabled": true
  }
}
```

### Required Fields

- `version`: Workflow version (semantic versioning: major.minor.patch)
- `steps`: Array of workflow steps (at least one step required)

### Optional Fields

- `dependencies`: Array of workflow names this workflow depends on
- `compensation`: Compensation configuration (for rollback support)

## Step Types

### Task Step

Executes a single task function.

```json
{
  "name": "step1",
  "type": "task",
  "task": "task_name",
  "input": {
    "key": "value"
  }
}
```

**Required Fields:**
- `name`: Step name (unique within workflow)
- `type`: Must be `"task"`
- `task`: Task identifier (must be registered in workflow engine)

**Optional Fields:**
- `input`: Step-specific input data (merged with workflow input and state)

### Parallel Step

Executes multiple steps in parallel.

```json
{
  "name": "parallel_step",
  "type": "parallel",
  "steps": [
    {
      "name": "step1",
      "type": "task",
      "task": "task1"
    },
    {
      "name": "step2",
      "type": "task",
      "task": "task2"
    }
  ]
}
```

**Required Fields:**
- `name`: Step name
- `type`: Must be `"parallel"`
- `steps`: Array of steps to execute in parallel

### Conditional Step

Executes steps conditionally based on workflow state.

```json
{
  "name": "conditional_step",
  "type": "conditional",
  "condition": {
    "operator": "equals",
    "field": "status",
    "value": "active"
  },
  "then": [
    {
      "name": "then_step",
      "type": "task",
      "task": "then_task"
    }
  ],
  "else": [
    {
      "name": "else_step",
      "type": "task",
      "task": "else_task"
    }
  ]
}
```

**Required Fields:**
- `name`: Step name
- `type`: Must be `"conditional"`
- `condition`: Condition expression (see Condition Expressions below)
- `then`: Array of steps to execute if condition is true

**Optional Fields:**
- `else`: Array of steps to execute if condition is false

**Condition Operators:**
- `equals`: Field equals value
- `not_equals`: Field does not equal value
- `exists`: Field exists in state

### Loop Step

Executes steps for each item in a collection.

```json
{
  "name": "loop_step",
  "type": "loop",
  "items": ["item1", "item2", "item3"],
  "steps": [
    {
      "name": "process_item",
      "type": "task",
      "task": "process_task"
    }
  ]
}
```

**Required Fields:**
- `name`: Step name
- `type`: Must be `"loop"`
- `items`: Array of items to iterate over (or `condition` for while loop)
- `steps`: Array of steps to execute for each item

### Retry Step

Retries steps on failure.

```json
{
  "name": "retry_step",
  "type": "retry",
  "max_retries": 3,
  "steps": [
    {
      "name": "step1",
      "type": "task",
      "task": "task_name"
    }
  ]
}
```

**Required Fields:**
- `name`: Step name
- `type`: Must be `"retry"`
- `max_retries`: Maximum number of retry attempts
- `steps`: Array of steps to retry

## Compensation

Workflows can define compensation logic for rollback (Saga pattern).

```json
{
  "compensation": {
    "enabled": true
  }
}
```

Each step can define compensation:

```json
{
  "name": "step1",
  "type": "task",
  "task": "task_name",
  "compensation": {
    "type": "task",
    "task": "compensation_task"
  }
}
```

**Compensation Types:**
- `task`: Execute a compensation task function
- `script`: Execute a compensation script

## Example Workflows

### Simple Sequential Workflow

```json
{
  "version": "1.0.0",
  "steps": [
    {
      "name": "validate",
      "type": "task",
      "task": "validate_task"
    },
    {
      "name": "process",
      "type": "task",
      "task": "process_task"
    },
    {
      "name": "notify",
      "type": "task",
      "task": "notify_task"
    }
  ]
}
```

### Workflow with Conditional Branching

```json
{
  "version": "1.0.0",
  "steps": [
    {
      "name": "check_status",
      "type": "task",
      "task": "check_status_task"
    },
    {
      "name": "conditional_process",
      "type": "conditional",
      "condition": {
        "operator": "equals",
        "field": "status",
        "value": "active"
      },
      "then": [
        {
          "name": "activate",
          "type": "task",
          "task": "activate_task"
        }
      ],
      "else": [
        {
          "name": "deactivate",
          "type": "task",
          "task": "deactivate_task"
        }
      ]
    }
  ]
}
```

### Workflow with Compensation

```json
{
  "version": "1.0.0",
  "compensation": {
    "enabled": true
  },
  "steps": [
    {
      "name": "create_resource",
      "type": "task",
      "task": "create_resource_task",
      "compensation": {
        "type": "task",
        "task": "delete_resource_task"
      }
    },
    {
      "name": "update_resource",
      "type": "task",
      "task": "update_resource_task",
      "compensation": {
        "type": "task",
        "task": "revert_resource_task"
      }
    }
  ]
}
```

## Workflow State

Workflows maintain state data that is shared between steps:

- `input_data`: Initial workflow input
- `state_data`: Shared state between steps (updated by each step)
- `output_data`: Final workflow output (populated on completion)

Each step receives:
- Workflow `input_data`
- Workflow `state_data`
- Step-specific `input`

Step output is merged into `state_data` for subsequent steps.

## Workflow Versioning

Workflows use semantic versioning (major.minor.patch):

- **Major**: Breaking changes (incompatible API changes)
- **Minor**: New features (backward compatible)
- **Patch**: Bug fixes (backward compatible)

Only one active version per workflow name. New instances use the active version.

## Workflow Dependencies

Workflows can depend on other workflows:

```json
{
  "version": "1.0.0",
  "dependencies": ["workflow1", "workflow2"],
  "steps": []
}
```

Dependencies must be registered before the dependent workflow. Circular dependencies are detected and rejected.

