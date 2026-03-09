## Assumptions & Scope

You should base your architectural decisions on the following assumptions.

### Assumptions
- This is an internal university system, not a public commercial product.
- **Expected users:**
  - Hundreds of students browsing events
  - Dozens of event organizers submitting events
  - A small number of staff administrators
- Concurrent usage is low to moderate.
- No strict real-time or high-availability requirements.
- The system is developed and maintained by a small team (2–4 engineers).
- Cloud hosting is available, but budget and operational resources are limited.

### Out of Scope
- Native mobile applications
- Public APIs for external partners
- Real-time chat or live streaming
- Complex role-based permission systems
- Advanced analytics or recommendation engines
