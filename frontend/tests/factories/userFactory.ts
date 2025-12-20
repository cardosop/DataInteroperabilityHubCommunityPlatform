/**
 * User Factory
 *
 * Factory for creating test User objects.
 */

import type { User, UserStatus, Role } from '@/lib/api/users'
import { generateId, generateUUID, randomEmail, randomDate, type FactoryOptions, type FactoryTrait } from './utils'

/**
 * User factory implementation
 */
class UserFactory implements FactoryTrait<User> {
  /**
   * Build a single User
   */
  build(options: FactoryOptions<User> = {}): User {
    const { overrides = {}, uniqueIds = true } = options
    const id = uniqueIds ? generateUUID() : 'test-user-1'
    const email = randomEmail()

    return {
      id,
      tenant: 'test-tenant',
      email,
      display_name: `Test User ${id.substring(0, 8)}`,
      status: 'ACTIVE' as UserStatus,
      is_platform_admin: false,
      roles: [],
      created_at: randomDate(new Date(Date.now() - 365 * 24 * 60 * 60 * 1000)),
      updated_at: new Date().toISOString(),
      ...overrides,
    }
  }

  buildMany(count: number, options: FactoryOptions<User> = {}): User[] {
    return Array.from({ length: count }, (_, index) =>
      this.build({
        ...options,
        overrides: {
          ...options.overrides,
          email: `user${index + 1}@test.com`,
          display_name: `Test User ${index + 1}`,
        },
      })
    )
  }

  buildSequence(builder: (index: number) => Partial<User>): User[] {
    const users: User[] = []
    let index = 0
    let user = this.build({ overrides: builder(index) })

    while (user) {
      users.push(user)
      index++
      const overrides = builder(index)
      if (overrides === null || overrides === undefined) {
        break
      }
      user = this.build({ overrides })
    }

    return users
  }

  /**
   * Build an ACTIVE user
   */
  active(options: FactoryOptions<User> = {}): User {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'ACTIVE' as UserStatus,
      },
    })
  }

  /**
   * Build an INVITED user
   */
  invited(options: FactoryOptions<User> = {}): User {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'INVITED' as UserStatus,
      },
    })
  }

  /**
   * Build a DISABLED user
   */
  disabled(options: FactoryOptions<User> = {}): User {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        status: 'DISABLED' as UserStatus,
      },
    })
  }

  /**
   * Build a platform admin user
   */
  platformAdmin(options: FactoryOptions<User> = {}): User {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        is_platform_admin: true,
        status: 'ACTIVE' as UserStatus,
      },
    })
  }

  /**
   * Build a user with roles
   */
  withRoles(roles: Role[], options: FactoryOptions<User> = {}): User {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        roles,
      },
    })
  }

  /**
   * Build a user with a specific tenant
   */
  withTenant(tenantId: string, options: FactoryOptions<User> = {}): User {
    return this.build({
      ...options,
      overrides: {
        ...options.overrides,
        tenant: tenantId,
      },
    })
  }
}

export const userFactory = new UserFactory()
export { UserFactory }

