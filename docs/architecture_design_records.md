# The Five Architecture Dimensions

---

## 1. System Roles & Communication

### Title
System Roles & Communication

### Status
Proposed

### Context
- Internal university system with low–moderate concurrency  
- Hundreds of students browsing, dozens of organizers submitting, few admins  
- Small team (2–4 engineers), limited ops/budget  
- No strict real-time or high-availability requirements  
- Avoid over-engineering (no public APIs, no complex permissions, etc.)

### Decision
**Client–Server**

### Alternatives Considered
- Event-Driven Architecture

### Consequences
#### Positive
- Simple mental model for CRUD workflows (submit → review → publish → browse/search)
- Easier authentication and role checks centralized in the server
- Fewer moving parts to deploy and maintain for a small team

#### Negative
- Tighter coupling between frontend and backend API compared to event-based systems
- Less flexible for future integrations/async workflows (notifications, analytics) if needed later

---

## 2. Deployment & Evolution

### Title
Deployment & Evolution

### Status
Proposed

### Context
- Small engineering team with limited operational capacity  
- Low–moderate load and internal-only usage  
- Need fast iteration and simple deployments

### Decision
**Monolith**

### Alternatives Considered
- Microservices

### Consequences
#### Positive
- Easier to develop, test, deploy, and debug
- Lower infrastructure complexity and cost
- Faster feature delivery for small teams

#### Negative
- Can become harder to scale organizationally if the system g
