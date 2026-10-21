/**
 * RuleTester pins for `mutation-guards/no-mutation-isloading` (W5.4).
 *
 * The planted-violation convention: a real violation flips RED, a
 * vacuous rule (one that reports nothing anywhere) is caught by the
 * valid + invalid pair below.
 */

'use strict';

const { RuleTester } = require('eslint');
const rule = require('./no-mutation-isloading.cjs');

const ruleTester = new RuleTester({
  languageOptions: {
    ecmaVersion: 2022,
    sourceType: 'module',
  },
});

ruleTester.run('mutation-guards/no-mutation-isloading', rule, {
  valid: [
    // Queries keep isLoading legitimately.
    'const { isLoading } = useQuery({ queryKey: ["x"], queryFn: f });',
    'const { isLoading } = useAssetListQuery({});',
    // Query-like hook names without the Mutation suffix are not flagged
    // (a name-based rule must not guess beyond the convention).
    'const { isLoading } = useSavedSearches();',
    // Mutations destructuring isPending are the correct pattern.
    'const { isPending } = useMutation({ mutationFn: f });',
    // Wrapper conventions too.
    'const { isPending, mutate } = useMutationWithNotification({ mutationFn: f });',
    'const { isPending } = useOptimisticMutation({ mutationFn: f });',
    // Property access (not a destructure) is out of scope.
    'const m = useMutation({ mutationFn: f }); const x = m.isLoading;',
  ],
  invalid: [
    {
      code: 'const { isLoading } = useMutation({ mutationFn: f });',
      errors: [{ messageId: 'useIsPending' }],
    },
    {
      code: 'const { isLoading, mutate } = useMutationWithNotification({ mutationFn: f });',
      errors: [{ messageId: 'useIsPending' }],
    },
    {
      code: 'const { isLoading } = useOptimisticMutation({ mutationFn: f });',
      errors: [{ messageId: 'useIsPending' }],
    },
    {
      code: 'const { isLoading } = useCreateContractMutation({});',
      errors: [{ messageId: 'useIsPending' }],
    },
  ],
});

console.log('mutation-guards/no-mutation-isloading RuleTester passed');
