# Moodle AI Assistant knowledge base

This demonstration service is an academic information assistant. It uses a role-aware data retrieval layer for the included, non-production student dataset and a separate document knowledge base for approved institutional material.

For student-specific information such as attendance, grades, academic profile, mentor details, and enrolled courses, the application retrieves only information permitted for the signed-in role. A student must not receive another student's records. Faculty queries are limited to the faculty scope, and administrators have the widest authorized scope.

The document knowledge base is source-attributed. Responses based on documents should cite the document name and page when available. If no approved source is found, the assistant should say so instead of inventing policy information.
