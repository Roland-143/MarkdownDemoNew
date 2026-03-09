# Tech Stack Decision Record — Campus Event Hub

## Title
Primary Technology Stack Selection for Campus Event Hub

## Status (Proposed / Accepted / Deprecated / Superseded)
Accepted

## Context
Campus Event Hub is an internal university web application with hundreds of student users, dozens of event organizers, and a small number of administrators. Usage is low to moderate, with no strict real-time or high-availability requirements. The system is built and maintained by a small team (2–4 engineers) with limited operational budget.

Architecture decisions already made:
- Client–Server communication
- Modular Monolith deployment
- Feature-Based code organization (vertical slices)
- Single shared database
- Primarily synchronous request/response interactions

The tech stack must support classic CRUD workflows (submit → review → publish → browse/search), be easy to deploy and maintain, and minimize operational complexity while remaining maintainable over multiple semesters.

## Decision
Use **Node.js (TypeScript) + Express + Server-Rendered Views (EJS/Pug) + PostgreSQL** as the primary tech stack.

## Alternatives Considered
- **Python + Streamlit + SQLAlchemy + PostgreSQL**
- **Spring Boot (MVC) + Thymeleaf/JSP + JPA (Hibernate) + PostgreSQL**

## Consequences

### Positive
- Clean fit for a synchronous client–server web application
- Simple monolithic deployment with a single backend service and database
- Fast development and iteration for a small team
- Easy to structure code into feature-based modules (submission, review, discovery)
- PostgreSQL provides strong consistency, indexing, and reliable search/filtering
- Low operational overhead and cost compared to enterprise-scale stacks

### Negative
- Express does not enforce architecture patterns, requiring team discipline to maintain feature boundaries
- Fewer built-in “batteries” than frameworks like Spring or Django (auth, admin tooling must be added manually if needed)
- If the system grows significantly, refactoring may be required to support more complex scaling needs
