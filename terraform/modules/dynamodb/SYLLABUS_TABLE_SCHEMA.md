# Syllabus Entities DynamoDB Table Schema

## Table Overview
**Table Name:** `{project_name}-{environment}-syllabus-entities`
**Billing Mode:** PAY_PER_REQUEST

## Primary Key Structure

### Partition Key (PK)
- **Format:** `SUBJECT#{subject_code}`
- **Example:** `SUBJECT#EXE401`
- **Purpose:** Groups all entities for a specific course

### Sort Key (SK)
- **Format:** `VERSION#{approved_date}#ENTITY#{entity_type}#{entity_id}`
- **Example:** `VERSION#2025-11-27T10:00:00Z#ENTITY#assessment#final_presentation`
- **Purpose:** Enables version-based queries and entity type filtering
- **Note:** `approved_date` uses ISO 8601 timestamp format (`YYYY-MM-DDTHH:MM:SSZ`) to support multiple versions on the same day

## Global Secondary Indexes

### GSI1: entity-type-index
**Purpose:** Query all entities of a specific type for a syllabus version

- **GSI1PK:** `SUBJECT#{subject_code}#VERSION#{approved_date}`
- **GSI1SK:** `ENTITY#{entity_type}#{entity_id}`
- **Projection:** ALL

**Use Cases:**
- Get all assessments for EXE401 version 2025-11-27T10:00:00Z
- Get all sessions for a specific syllabus version
- Get all CLOs for a course version

### GSI2: clo-session-index
**Purpose:** Find sessions that cover a specific CLO

- **GSI2PK:** `SUBJECT#{subject_code}#CLO#{clo_id}`
- **GSI2SK:** `SESSION#{session_number}`
- **Projection:** ALL

**Use Cases:**
- Find all sessions that teach CLO1
- Map CLOs to their teaching sessions
- Analyze CLO coverage across sessions

## Access Patterns Supported

| Pattern | Description | Index Used |
|---------|-------------|------------|
| AP1 | Get latest version of syllabus | Primary Key (PK query) |
| AP2 | Get all entities by version | Primary Key (PK + SK begins_with) |
| AP3 | Get assessments for a version | GSI1 (entity-type-index) |
| AP4 | Get sessions by CLO | GSI2 (clo-session-index) |
| AP5 | Get CLOs for a version | GSI1 (entity-type-index) |
| AP6 | List all versions | Primary Key (PK query) |
| AP7 | Get course info | Primary Key (PK + SK exact match) |

## Entity Types

1. **course_info** - Course metadata (credits, instructor, etc.)
2. **clo** - Course Learning Outcomes
3. **session** - Class sessions/meetings
4. **assessment** - Grading components (exams, projects, etc.)
5. **material** - Learning materials (textbooks, slides, etc.)

## Example Items

### Course Info
```json
{
  "PK": "SUBJECT#EXE401",
  "SK": "VERSION#2025-11-27T10:00:00Z#ENTITY#course_info#main",
  "GSI1PK": "SUBJECT#EXE401#VERSION#2025-11-27T10:00:00Z",
  "GSI1SK": "ENTITY#course_info#main",
  "entity_type": "course_info",
  "course_name": "Graduation Thesis Project",
  "credits": 10
}
```

### Assessment
```json
{
  "PK": "SUBJECT#EXE401",
  "SK": "VERSION#2025-11-27T10:00:00Z#ENTITY#assessment#final_exam",
  "GSI1PK": "SUBJECT#EXE401#VERSION#2025-11-27T10:00:00Z",
  "GSI1SK": "ENTITY#assessment#final_exam",
  "entity_type": "assessment",
  "weight_percentage": 40,
  "clo_mapping": ["CLO1", "CLO2", "CLO3"]
}
```

### Session
```json
{
  "PK": "SUBJECT#EXE401",
  "SK": "VERSION#2025-11-27T10:00:00Z#ENTITY#session#1",
  "GSI1PK": "SUBJECT#EXE401#VERSION#2025-11-27T10:00:00Z",
  "GSI1SK": "ENTITY#session#1",
  "GSI2PK": "SUBJECT#EXE401#CLO#CLO1",
  "GSI2SK": "SESSION#1",
  "entity_type": "session",
  "session_number": 1,
  "topics": ["Project kickoff"],
  "clo_coverage": ["CLO1", "CLO2"]
}
```

## Deployment

To deploy this table:

```bash
cd terraform
terraform init
terraform plan
terraform apply
```

The table will be created with:
- PAY_PER_REQUEST billing (no capacity planning needed)
- Two Global Secondary Indexes for efficient querying
- Appropriate tags for resource management
