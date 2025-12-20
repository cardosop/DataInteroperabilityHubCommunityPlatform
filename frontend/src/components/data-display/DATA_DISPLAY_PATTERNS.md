# Data Display Patterns

This document describes the data display patterns implemented for the Data Interoperability Hub frontend.

## Table of Contents

1. [Table Sorting](#table-sorting)
2. [Table Filtering](#table-filtering)
3. [Infinite Scroll](#infinite-scroll)
4. [Virtual Scrolling](#virtual-scrolling)
5. [Pagination](#pagination)
6. [Data Export](#data-export)

## Table Sorting

### Features

- Click header to sort (asc → desc → unsorted)
- Visual indicators with icons (ArrowUpward, ArrowDownward, UnfoldMore)
- Supports string, number, and date sorting
- Custom sort functions per column

### Usage

#### Using EnhancedTable Component

```tsx
import { EnhancedTable } from '@/components/data-display/Table'

const columns = [
  { id: 'name', label: 'Name', sortable: true },
  { id: 'email', label: 'Email', sortable: true },
  { id: 'created', label: 'Created', sortable: true },
]

<EnhancedTable
  columns={columns}
  data={users}
  sortable
/>
```

#### Using useTableSort Hook

```tsx
import { useTableSort } from '@/hooks/useTableSort'

const { sortedData, handleSort, sortState } = useTableSort(users, {
  initialSortColumn: 'name',
  initialSortDirection: 'asc',
  getSortValue: (row, columnId) => {
    // Custom sort logic
    return row[columnId]
  },
})
```

## Table Filtering

### Features

- Global search across multiple columns
- Column-specific filters
- Custom filter functions
- Active filter count display

### Usage

#### Using EnhancedTable Component

```tsx
<EnhancedTable
  columns={columns}
  data={users}
  filterable
  globalSearchColumns={['name', 'email']}
  searchPlaceholder="Search users..."
/>
```

#### Using useTableFilter Hook

```tsx
import { useTableFilter } from '@/hooks/useTableFilter'

const {
  filteredData,
  globalSearch,
  setGlobalSearch,
  setColumnFilter,
  activeFilterCount,
} = useTableFilter(users, {
  globalSearchColumns: ['name', 'email'],
  globalSearchFn: (row, searchValue) => {
    // Custom global search logic
    return row.name.toLowerCase().includes(searchValue.toLowerCase())
  },
})
```

#### Combining Sorting and Filtering

```tsx
// First filter
const { filteredData } = useTableFilter(users, {
  globalSearchColumns: ['name', 'email'],
})

// Then sort filtered data
const { sortedData } = useTableSort(filteredData, {
  initialSortColumn: 'name',
})
```

## Infinite Scroll

### Features

- Automatically loads more data when scrolling near bottom
- Uses Intersection Observer for performance
- Configurable threshold distance
- Prevents rapid firing with loading state

### Usage

```tsx
import { useInfiniteScroll } from '@/hooks/useInfiniteScroll'

function UserList() {
  const { data, fetchNextPage, hasNextPage, isFetching } = useQuery(...)

  const { sentinelRef } = useInfiniteScroll(
    () => fetchNextPage(),
    {
      hasMore: hasNextPage,
      isLoading: isFetching,
      threshold: 100, // Load when 100px from bottom
    }
  )

  return (
    <div>
      {data.pages.flat().map(user => (
        <UserCard key={user.id} user={user} />
      ))}
      <div ref={sentinelRef} />
      {isFetching && <Loading />}
    </div>
  )
}
```

## Virtual Scrolling

### Features

- Renders only visible items for large lists
- Configurable item height
- Overscan buffer for smooth scrolling
- Scroll to index functionality

### Usage

#### Using VirtualList Component

```tsx
import { VirtualList } from '@/components/data-display/VirtualList'

<VirtualList
  items={users}
  itemHeight={50}
  containerHeight={400}
  renderItem={(user) => (
    <div style={{ padding: '12px', borderBottom: '1px solid #eee' }}>
      {user.name}
    </div>
  )}
  getItemKey={(user) => user.id}
/>
```

#### Using useVirtualScroll Hook

```tsx
import { useVirtualScroll } from '@/hooks/useVirtualScroll'

const { virtualItems, totalHeight, containerRef } = useVirtualScroll(
  users.length,
  {
    itemHeight: 50,
    containerHeight: 400,
    overscan: 3,
  }
)

return (
  <div ref={containerRef} style={{ height: 400, overflow: 'auto' }}>
    <div style={{ height: totalHeight, position: 'relative' }}>
      {virtualItems.map(({ index, top }) => (
        <div
          key={users[index].id}
          style={{
            position: 'absolute',
            top,
            height: 50,
          }}
        >
          {users[index].name}
        </div>
      ))}
    </div>
  </div>
)
```

## Pagination

### Features

- Page navigation (first, prev, next, last)
- Page number buttons with ellipsis
- Page size selector (10, 25, 50, 100)
- Item count display
- Accessible with ARIA labels

### Usage

#### Using EnhancedPagination Component

```tsx
import { EnhancedPagination } from '@/components/navigation/Pagination'

const [page, setPage] = useState(1)
const [pageSize, setPageSize] = useState(25)
const totalPages = Math.ceil(totalItems / pageSize)

<EnhancedPagination
  page={page}
  totalPages={totalPages}
  onPageChange={setPage}
  pageSize={pageSize}
  onPageSizeChange={setPageSize}
  totalItems={totalItems}
  pageSizeOptions={[10, 25, 50, 100]}
  showItemCount
/>
```

#### Using Basic Pagination Component

```tsx
import { Pagination } from '@/components/navigation/Pagination'

<Pagination
  page={page}
  totalPages={totalPages}
  onPageChange={setPage}
  siblingCount={1}
  showFirstLast
  showPrevNext
/>
```

## Data Export

### Features

- Export to CSV format
- Export to JSON format
- Export to Excel format (CSV with .xlsx extension)
- Custom data formatters
- Proper CSV escaping

### Usage

#### Export to CSV

```tsx
import { exportToCSV } from '@/lib/utils/dataExport'

const handleExport = () => {
  exportToCSV(users, {
    filename: 'users-export',
    includeHeaders: true,
  })
}
```

#### Export to JSON

```tsx
import { exportToJSON } from '@/lib/utils/dataExport'

const handleExport = () => {
  exportToJSON(users, {
    filename: 'users-export',
    pretty: true, // Formatted JSON
  })
}
```

#### Export to Excel

```tsx
import { exportToExcel } from '@/lib/utils/dataExport'

const handleExport = () => {
  exportToExcel(users, {
    filename: 'users-export',
  })
}
```

#### Export with Custom Formatter

```tsx
import { exportData } from '@/lib/utils/dataExport'

const handleExport = () => {
  exportData(users, {
    format: 'csv',
    filename: 'users-export',
    formatter: (user) => ({
      'Full Name': user.firstName + ' ' + user.lastName,
      'Email Address': user.email,
      'Created Date': new Date(user.createdAt).toLocaleDateString(),
    }),
  })
}
```

## Combining Patterns

### Table with Sorting, Filtering, and Pagination

```tsx
function DataTable() {
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(25)

  // Filter first
  const { filteredData, globalSearch, setGlobalSearch } = useTableFilter(
    allData,
    { globalSearchColumns: ['name', 'email'] }
  )

  // Then sort
  const { sortedData } = useTableSort(filteredData)

  // Then paginate
  const paginatedData = useMemo(() => {
    const start = (page - 1) * pageSize
    return sortedData.slice(start, start + pageSize)
  }, [sortedData, page, pageSize])

  const totalPages = Math.ceil(filteredData.length / pageSize)

  return (
    <>
      <EnhancedTable
        columns={columns}
        data={paginatedData}
        sortable
        filterable
        globalSearch={globalSearch}
        onGlobalSearchChange={setGlobalSearch}
      />
      <EnhancedPagination
        page={page}
        totalPages={totalPages}
        onPageChange={setPage}
        pageSize={pageSize}
        onPageSizeChange={setPageSize}
        totalItems={filteredData.length}
      />
    </>
  )
}
```

### Virtual List with Infinite Scroll

```tsx
function VirtualInfiniteList() {
  const { data, fetchNextPage, hasNextPage, isFetching } = useInfiniteQuery(...)
  const allItems = data.pages.flat()

  const { sentinelRef } = useInfiniteScroll(
    () => fetchNextPage(),
    { hasMore: hasNextPage, isLoading: isFetching }
  )

  return (
    <VirtualList
      items={allItems}
      itemHeight={50}
      containerHeight={400}
      renderItem={(item) => <ItemCard item={item} />}
      loadingComponent={isFetching ? <Loading /> : null}
      isLoading={isFetching}
    />
  )
}
```

## Best Practices

1. **Performance**: Use virtual scrolling for lists with 100+ items
2. **Filtering**: Apply filters before sorting for better performance
3. **Pagination**: Use server-side pagination for large datasets
4. **Export**: Format data appropriately before exporting
5. **Accessibility**: All components include ARIA labels and keyboard navigation

## Type Safety

All patterns are fully typed with TypeScript:

```tsx
import type {
  SortDirection,
  UseTableSortReturn,
  UseTableFilterReturn,
  VirtualItem,
} from '@/hooks'
```

## See Also

- [Table Component Documentation](./Table/README.md)
- [Pagination Component Documentation](../navigation/Pagination/README.md)
- [Hooks Documentation](../../hooks/README.md)

