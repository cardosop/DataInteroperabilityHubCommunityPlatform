# Documentation Style Guide

**Last Updated**: 2026-01-26  
**Purpose**: Ensure consistency and quality across all documentation

## General Principles

### Clarity
- Write clearly and concisely
- Use simple language when possible
- Avoid jargon unless necessary (and then define it)
- Use active voice

### Accuracy
- Ensure all information is accurate and up-to-date
- Test all code examples
- Verify all links work
- Update documentation when features change

### Completeness
- Cover all aspects of the topic
- Include prerequisites
- Provide examples
- Include troubleshooting sections when appropriate

### Consistency
- Use consistent terminology
- Follow naming conventions
- Use consistent formatting
- Maintain consistent structure

## Structure

### Document Headers

Every document should start with:

```markdown
# [Document Title]

**Last Updated**: [Date]  
**Owner**: [Team/Individual]  
**Status**: [Draft/Review/Approved]
```

### Table of Contents

For documents longer than 500 lines, include a table of contents:

```markdown
## Table of Contents

1. [Section 1](#section-1)
2. [Section 2](#section-2)
   - [Subsection 2.1](#subsection-21)
```

### Sections

Use clear, descriptive section headings:

```markdown
## Main Section

### Subsection

#### Sub-subsection
```

## Formatting

### Code Blocks

Always specify the language for code blocks:

````markdown
```python
def example():
    return "Hello, World!"
```
````

### Inline Code

Use backticks for:
- Function names
- Variable names
- File names
- Command names
- API endpoints
- Configuration values

Example: Use the `get_data()` function to retrieve data.

### Emphasis

- **Bold**: For important terms, key concepts, or warnings
- *Italic*: For emphasis or foreign terms
- `Code`: For code, commands, or technical terms

### Lists

Use ordered lists for sequential steps:

```markdown
1. First step
2. Second step
3. Third step
```

Use unordered lists for non-sequential items:

```markdown
- Item 1
- Item 2
- Item 3
```

### Tables

Use tables for structured data:

```markdown
| Column 1 | Column 2 | Column 3 |
|----------|----------|----------|
| Value 1  | Value 2  | Value 3  |
```

## Terminology

### Consistent Terms

Use these terms consistently:

- **ODPS**: Open Data Product Standard (use full term on first mention, then ODPS)
- **Data Product**: Not "data product" (capitalize when referring to ODPS concept)
- **API**: Application Programming Interface (use full term on first mention, then API)
- **WebSocket**: Not "websocket" or "Web Socket"
- **Event Bus**: Not "eventbus" or "event-bus"

### Naming Conventions

- **Files**: Use UPPERCASE_WITH_UNDERSCORES.md for main docs
- **Functions**: Use snake_case
- **Classes**: Use PascalCase
- **Variables**: Use snake_case

## Code Examples

### Best Practices

1. **Always test code examples** before including them
2. **Include expected output** when relevant
3. **Use realistic examples** that users can actually use
4. **Add comments** to explain complex parts
5. **Show error handling** when appropriate

### Example Format

```markdown
### Example: Creating a Data Product

**Request**:
```bash
curl -X POST "https://api.example.com/v1/data-products" \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Example Product",
    "version": "1.0.0"
  }'
```

**Response**:
```json
{
  "id": "123",
  "name": "Example Product",
  "version": "1.0.0",
  "status": "created"
}
```
```

## Links and References

### Internal Links

Use relative paths for internal documentation:

```markdown
[API Reference](./API_REFERENCE.md)
[Architecture Guide](../ARCHITECTURE.md)
```

### External Links

Always include the full URL and make it clear it's external:

```markdown
[ODPS Specification](https://opendataproducts.org/specification)
```

### Reference Sections

Include a "References" section at the end of documents:

```markdown
## References

- [Related Documentation 1](./path/to/doc.md)
- [External Resource](https://example.com)
```

## Images and Diagrams

### Best Practices

1. **Use descriptive file names**: `odps-workflow-diagram.png`
2. **Include alt text**: `![ODPS Workflow Diagram](./images/odps-workflow-diagram.png)`
3. **Store in appropriate directory**: `docs/images/` or `docs/diagrams/`
4. **Keep file sizes reasonable**: Optimize images for web

## Checklists and Tasks

Use checkboxes for actionable items:

```markdown
- [ ] Task 1
- [ ] Task 2
- [x] Completed task
```

## Warnings and Notes

### Warning

Use for important warnings:

```markdown
> **Warning**: This action cannot be undone.
```

### Note

Use for additional information:

```markdown
> **Note**: This feature requires additional configuration.
```

### Tip

Use for helpful tips:

```markdown
> **Tip**: You can use this shortcut to save time.
```

## Version Information

### Document Version

Include version information in document headers:

```markdown
**Version**: 1.0.0
**Last Updated**: 2026-01-26
```

### API Versioning

When documenting APIs, always specify the version:

```markdown
## API v1

[API documentation]

## API v2

[API documentation]
```

## Review Checklist

Before submitting documentation for review, check:

- [ ] All information is accurate
- [ ] All code examples work
- [ ] All links work
- [ ] Terminology is consistent
- [ ] Formatting follows style guide
- [ ] Examples are clear and useful
- [ ] Prerequisites are listed
- [ ] Troubleshooting section included (if needed)
- [ ] References section included

## Common Mistakes to Avoid

1. **Outdated information**: Always verify information is current
2. **Broken links**: Test all links before publishing
3. **Untested code**: Always test code examples
4. **Inconsistent terminology**: Use the style guide
5. **Missing context**: Provide enough context for users
6. **Overly complex examples**: Keep examples simple and focused
7. **Missing prerequisites**: Always list what's needed first
8. **No troubleshooting**: Include common issues and solutions

## Questions?

If you have questions about documentation style, contact:
- Documentation Team: [contact]
- Tech Lead: [contact]
