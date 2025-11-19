# Contact Lists

Contact lists are a powerful way to organize and segment your contacts. They enable fine-grained control over your audience and provide a foundation for targeted communication and engagement strategies.

## Overview

Contact lists allow you to group contacts into logical collections based on shared characteristics, interests, or engagement levels. A contact can belong to multiple lists, and lists can be used to filter and target specific segments of your audience when sending communications or running campaigns.

Contact lists are an optional but recommended feature for managing your contacts. While you can work with contacts individually, lists provide a scalable way to manage large audiences and enable more sophisticated communication workflows.

## Core Concepts

### List Structure

Each contact list has the following attributes:

- **Name**: A descriptive name for the list (e.g., "Newsletter Subscribers", "VIP Customers", "Beta Testers")
- **Description**: Optional text that explains the purpose or criteria for the list
- **Created By**: The user who created the list
- **Timestamps**: Automatic tracking of when the list was created and last updated

### Many-to-Many Relationship

Contact lists use a many-to-many relationship with contacts:

- A contact can belong to **multiple lists** (e.g., a contact can be in both "Newsletter Subscribers" and "Product Updates")
- A list can contain **many contacts**
- This relationship is managed through the `ContactListMember` junction table

### Soft Delete

Both contact lists and list memberships support soft deletion:

- Deleting a list marks it as deleted but preserves the data
- Removing a contact from a list soft-deletes the membership
- This allows for data recovery and audit trails

## Use Cases

Contact lists can be used for various purposes:

### 1. **Audience Segmentation**

Organize contacts by characteristics such as:
- Geographic location
- Industry or company type
- Product interests
- Subscription preferences
- Customer tier (e.g., free, paid, enterprise)

### 2. **Targeted Communications**

Send messages to specific segments:
- Product announcements to users who opted in for updates
- Regional newsletters to contacts in specific areas
- Special offers to high-value customers

### 3. **Lifecycle Management**

Track contacts through different stages:
- New subscribers
- Active users
- At-risk customers
- Churned users

### 4. **Event-Based Lists**

Group contacts based on events or actions:
- Attendees of a webinar
- Participants in a beta program
- People who downloaded specific resources

## API Operations

### Creating a Contact List

Create a new contact list:

```http
POST /contact-lists
Content-Type: application/json

{
  "name": "Newsletter Subscribers",
  "description": "Contacts who have subscribed to our newsletter"
}
```

**Response:**

```json
{
  "id": "550e8400-e29b-41d4-a716-446655440000",
  "name": "Newsletter Subscribers",
  "description": "Contacts who have subscribed to our newsletter",
  "created_by_id": "123e4567-e89b-12d3-a456-426614174000",
  "created_at": "2025-01-15T10:00:00Z",
  "updated_at": "2025-01-15T10:00:00Z"
}
```

### Listing Contact Lists

Get all contact lists with pagination:

```http
GET /contact-lists?page=1&size=20
```

### Getting a Specific List

Retrieve details of a contact list:

```http
GET /contact-lists/{contact_list_id}
```

### Updating a Contact List

Update list name or description:

```http
PUT /contact-lists/{contact_list_id}
Content-Type: application/json

{
  "name": "Weekly Newsletter Subscribers",
  "description": "Updated description"
}
```

### Deleting a Contact List

Soft delete a contact list:

```http
DELETE /contact-lists/{contact_list_id}
```

**Note:** Deleted lists can be restored if needed, preserving historical data.

## Member Management

### Adding Contacts to a List

Add one or more contacts to a list:

```http
POST /contact-lists/{contact_list_id}/members
Content-Type: application/json

{
  "contact_ids": [
    "550e8400-e29b-41d4-a716-446655440001",
    "550e8400-e29b-41d4-a716-446655440002"
  ]
}
```

**Response:**

```json
{
  "message": "Successfully added 2 contact(s) to the list",
  "added_count": 2,
  "requested_count": 2
}
```

### Removing a Contact from a List

Remove a single contact from a list:

```http
DELETE /contact-lists/{contact_list_id}/members/{contact_id}
```

### Getting List Members

Retrieve all contacts in a list:

```http
GET /contact-lists/{contact_list_id}/members
```

**Response:**

```json
{
  "contact_list_id": "550e8400-e29b-41d4-a716-446655440000",
  "members": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "email": "[email protected]",
      "first_name": "John",
      "last_name": "Doe",
      ...
    }
  ]
}
```

### Getting Member Count

Get the number of contacts in a list:

```http
GET /contact-lists/{contact_list_id}/members/count
```

**Response:**

```json
{
  "contact_list_id": "550e8400-e29b-41d4-a716-446655440000",
  "count": 42
}
```

### Clearing All Members

Remove all contacts from a list:

```http
DELETE /contact-lists/{contact_list_id}/members
```

### Getting Lists for a Contact

Find all lists that a contact belongs to:

```http
GET /contact-lists/contacts/{contact_id}/contact-lists
```

### Checking Membership

Verify if a contact is in a specific list:

```http
GET /contact-lists/{contact_list_id}/members/{contact_id}/is-member
```

**Response:**

```json
{
  "contact_list_id": "550e8400-e29b-41d4-a716-446655440000",
  "contact_id": "550e8400-e29b-41d4-a716-446655440001",
  "is_member": true
}
```

## Best Practices

### List Organization

1. **Use Descriptive Names**: Choose clear, self-explanatory names that indicate the list's purpose
2. **Add Descriptions**: Document the criteria or purpose of each list for team members
3. **Avoid Overlap**: Design lists so they represent distinct segments when possible
4. **Regular Cleanup**: Periodically review and archive or delete unused lists

### Member Management

1. **Bulk Operations**: Use the bulk add endpoint when adding multiple contacts to improve performance
2. **Idempotency**: The system handles duplicate memberships gracefully - adding a contact who's already in a list won't create duplicates
3. **Soft Delete Benefits**: Removed memberships are soft-deleted, allowing for audit trails and potential restoration

### Data Integrity

1. **Validation**: The system validates that both the contact and list exist before creating memberships
2. **Consistency**: Contact list operations maintain referential integrity
3. **Soft Deletes**: Use soft deletion to preserve historical data and relationships

## Implementation Details

### Database Schema

Contact lists are implemented using three main tables:

- **`contact_lists`**: Stores list metadata (name, description, created_by_id)
- **`contacts`**: Stores contact information
- **`contact_list_members`**: Junction table linking contacts to lists

### Service Layer

The `ContactListService` provides methods for:

- CRUD operations on lists
- Member management (add, remove, query)
- Soft delete and restore functionality
- Search and filtering capabilities

### Relationship Management

Memberships are managed through the `ContactListMember` model, which tracks:

- The list ID
- The contact ID
- Timestamps (created_at, updated_at, deleted_at)

This design allows for:
- Tracking when contacts were added to lists
- Soft deletion of memberships
- Querying active memberships efficiently

## Future Enhancements

Potential future features for contact lists include:

- **List Visibility**: Public vs. private lists for preference center functionality
- **List Colors/Tags**: Visual organization and categorization
- **Automated Rules**: Auto-add contacts to lists based on properties or events
- **List Analytics**: Track engagement metrics per list
- **Import/Export**: Bulk import contacts directly into lists from CSV files
- **Preference Centers**: Allow contacts to manage their own list subscriptions

## Related Documentation

- [Database Design](./database.md) - Database architecture and design decisions
- [API Patterns](./api-patterns.md) - API router patterns and conventions

