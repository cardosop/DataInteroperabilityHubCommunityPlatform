"""
Comprehensive E2E tests for Marketplace Use Cases.

Covers:
- Publication: publish, unpublish, update listing
- Purchase: purchase asset, approve/reject order
- Entitlement: grant, revoke, check status

Uses REAL services (no mocks/stubs).
"""
import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from django.utils import timezone

from hub.apps.tenants.models import Tenant, KYCStatus
from hub.apps.assets.models import Asset, AssetStatus
from hub.apps.marketplace.models import (
    Listing, ListingStatus, PricingModel,
    Order, OrderStatus,
    Entitlement, EntitlementStatus
)
from hub.apps.marketplace.access_utils import check_entitlement

from .conftest import E2ETestBase


pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e5]
User = get_user_model()


class MarketplacePublicationUseCasesTest(E2ETestBase):
    """Test marketplace publication use cases: publish, unpublish, update listing"""
    
    def setUp(self):
        """Set up test fixtures with provider tenant"""
        super().setUp()
        
        # Create provider tenant with verified KYC
        self.provider_tenant = Tenant.objects.create(
            name="Provider Tenant",
            slug="provider-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.provider_user = User.objects.create_user(
            email="provider@example.com",
            password="testpass123",
            tenant=self.provider_tenant
        )
        
        self.provider_client = APIClient()
        self.provider_client.force_authenticate(user=self.provider_user)
        
        # Create active asset for provider
        self.asset = Asset.objects.create(
            tenant=self.provider_tenant,
            key="public-asset",
            name="Public Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.provider_user
        )
    
    def test_publish_listing_success(self):
        """Test publishing a listing successfully"""
        # Step 1: Create listing in DRAFT status
        listing_response = self.provider_client.post(
            '/api/v1/marketplace/listings/',
            {
                'asset_id': str(self.asset.id),
                'title': 'Public Asset Listing',
                'short_description': 'A valuable dataset for testing',
                'pricing_model': PricingModel.FREE_AUTO_APPROVE,
                'price_amount': 0.0
            },
            format='json'
        )
        self.assertEqual(listing_response.status_code, status.HTTP_201_CREATED)
        listing_id = listing_response.data['id']
        
        # Verify listing is in DRAFT status
        listing = Listing.objects.get(id=listing_id)
        self.assertEqual(listing.status, ListingStatus.DRAFT)
        self.assertIsNone(listing.published_at)
        
        # Step 2: Publish listing
        publish_response = self.provider_client.patch(
            f'/api/v1/marketplace/listings/{listing_id}/',
            {'status': ListingStatus.PUBLISHED},
            format='json'
        )
        self.assertEqual(publish_response.status_code, status.HTTP_200_OK)
        
        # Verify listing is published
        listing.refresh_from_db()
        self.assertEqual(listing.status, ListingStatus.PUBLISHED)
        self.assertIsNotNone(listing.published_at)
        self.assertEqual(listing.metadata_json.get('title'), 'Public Asset Listing')
    
    def test_unpublish_listing_success(self):
        """Test unpublishing (unlisting) a published listing"""
        # Step 1: Create and publish listing
        listing_response = self.provider_client.post(
            '/api/v1/marketplace/listings/',
            {
                'asset_id': str(self.asset.id),
                'title': 'Unpublish Test Listing',
                'short_description': 'Test description',
                'pricing_model': PricingModel.FREE_AUTO_APPROVE,
                'price_amount': 0.0
            },
            format='json'
        )
        listing_id = listing_response.data['id']
        
        # Publish listing
        self.provider_client.patch(
            f'/api/v1/marketplace/listings/{listing_id}/',
            {'status': ListingStatus.PUBLISHED},
            format='json'
        )
        
        listing = Listing.objects.get(id=listing_id)
        self.assertEqual(listing.status, ListingStatus.PUBLISHED)
        
        # Step 2: Unpublish (unlist) the listing
        unpublish_response = self.provider_client.patch(
            f'/api/v1/marketplace/listings/{listing_id}/',
            {'status': ListingStatus.UNLISTED},
            format='json'
        )
        self.assertEqual(unpublish_response.status_code, status.HTTP_200_OK)
        
        # Verify listing is unlisted
        listing.refresh_from_db()
        self.assertEqual(listing.status, ListingStatus.UNLISTED)
        # published_at should remain set (historical record)
        self.assertIsNotNone(listing.published_at)
    
    def test_update_listing_success(self):
        """Test updating a listing"""
        # Step 1: Create listing
        listing_response = self.provider_client.post(
            '/api/v1/marketplace/listings/',
            {
                'asset_id': str(self.asset.id),
                'title': 'Original Title',
                'short_description': 'Original description',
                'pricing_model': PricingModel.FREE_AUTO_APPROVE,
                'price_amount': 0.0
            },
            format='json'
        )
        listing_id = listing_response.data['id']
        
        # Step 2: Update listing
        update_response = self.provider_client.patch(
            f'/api/v1/marketplace/listings/{listing_id}/',
            {
                'title': 'Updated Title',
                'short_description': 'Updated description',
                'price_amount': 99.99,
                'currency': 'USD'
            },
            format='json'
        )
        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        
        # Verify listing is updated
        listing = Listing.objects.get(id=listing_id)
        listing.refresh_from_db()
        self.assertEqual(listing.metadata_json.get('title'), 'Updated Title')
        self.assertEqual(listing.metadata_json.get('short_description'), 'Updated description')
        if 'price_amount' in listing.metadata_json:
            self.assertEqual(float(listing.metadata_json.get('price_amount', 0)), 99.99)
    
    def test_publish_listing_with_invalid_asset_fails(self):
        """Test that publishing listing with inactive asset fails"""
        # Create inactive asset
        inactive_asset = Asset.objects.create(
            tenant=self.provider_tenant,
            key="inactive-asset",
            name="Inactive Asset",
            status=AssetStatus.DRAFT,
            created_by=self.provider_user
        )
        
        # Create listing - might fail during creation if view validates asset status
        listing_response = self.provider_client.post(
            '/api/v1/marketplace/listings/',
            {
                'asset_id': str(inactive_asset.id),
                'title': 'Inactive Asset Listing',
                'short_description': 'Test',
                'pricing_model': PricingModel.FREE_AUTO_APPROVE,
                'price_amount': 0.0
            },
            format='json'
        )
        
        # Listing creation might fail immediately, or succeed but publishing should fail
        if listing_response.status_code == status.HTTP_201_CREATED:
            listing_id = listing_response.data['id']
            publish_response = self.provider_client.patch(
                f'/api/v1/marketplace/listings/{listing_id}/',
                {'status': ListingStatus.PUBLISHED},
                format='json'
            )
            # Should fail because asset is not ACTIVE
            self.assertIn(publish_response.status_code, [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ])
        else:
            # Listing creation failed because asset is not active - this is also valid
            self.assertIn(listing_response.status_code, [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ])
    
    def test_publish_listing_without_title_fails(self):
        """Test that publishing listing without title fails"""
        # Create listing without title
        listing_response = self.provider_client.post(
            '/api/v1/marketplace/listings/',
            {
                'asset_id': str(self.asset.id),
                'short_description': 'No title listing',
                'pricing_model': PricingModel.FREE_AUTO_APPROVE,
                'price_amount': 0.0
            },
            format='json'
        )
        
        # Listing creation might fail if title is required, or succeed but publishing should fail
        if listing_response.status_code == status.HTTP_201_CREATED:
            listing_id = listing_response.data['id']
            publish_response = self.provider_client.patch(
                f'/api/v1/marketplace/listings/{listing_id}/',
                {'status': ListingStatus.PUBLISHED},
                format='json'
            )
            # Should fail because listing has no title
            self.assertIn(publish_response.status_code, [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ])
        else:
            # Listing creation failed because title is required - this is also valid
            self.assertIn(listing_response.status_code, [
                status.HTTP_400_BAD_REQUEST,
                status.HTTP_422_UNPROCESSABLE_ENTITY
            ])


class MarketplacePurchaseUseCasesTest(E2ETestBase):
    """Test marketplace purchase use cases: purchase asset, approve/reject order"""
    
    def setUp(self):
        """Set up test fixtures with provider and consumer tenants"""
        super().setUp()
        
        # Provider tenant (seller)
        self.provider_tenant = Tenant.objects.create(
            name="Provider Tenant",
            slug="provider-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.provider_user = User.objects.create_user(
            email="provider@example.com",
            password="testpass123",
            tenant=self.provider_tenant
        )
        
        self.provider_client = APIClient()
        self.provider_client.force_authenticate(user=self.provider_user)
        
        # Consumer tenant (buyer)
        self.consumer_tenant = Tenant.objects.create(
            name="Consumer Tenant",
            slug="consumer-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.consumer_user = User.objects.create_user(
            email="consumer@example.com",
            password="testpass123",
            tenant=self.consumer_tenant
        )
        
        self.consumer_client = APIClient()
        self.consumer_client.force_authenticate(user=self.consumer_user)
        
        # Create active asset and published listing
        self.asset = Asset.objects.create(
            tenant=self.provider_tenant,
            key="purchasable-asset",
            name="Purchasable Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.provider_user
        )
        
        self.listing = Listing.objects.create(
            tenant=self.provider_tenant,
            asset=self.asset,
            pricing_model=PricingModel.REQUEST_APPROVAL,  # Requires manual approval
            status=ListingStatus.PUBLISHED,
            metadata_json={
                'title': 'Purchasable Asset',
                'short_description': 'A valuable dataset',
                'price_amount': 99.99,
                'currency': 'USD'
            }
        )
    
    def test_purchase_asset_success(self):
        """Test purchasing an asset (creating an order)"""
        # Step 1: Consumer creates order
        order_response = self.consumer_client.post(
            '/api/v1/marketplace/orders/',
            {'listing_id': str(self.listing.id)},
            format='json'
        )
        self.assertEqual(order_response.status_code, status.HTTP_201_CREATED)
        
        # Get order ID from response
        order_data = order_response.data.get('order', order_response.data)
        order_id = order_data['id']
        
        # Verify order created
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, OrderStatus.REQUESTED)
        self.assertEqual(order.tenant, self.consumer_tenant)
        self.assertEqual(order.listing, self.listing)
        self.assertEqual(order.created_by, self.consumer_user)
    
    def test_approve_order_success(self):
        """Test approving an order (provider side)"""
        # Step 1: Consumer creates order
        order_response = self.consumer_client.post(
            '/api/v1/marketplace/orders/',
            {'listing_id': str(self.listing.id)},
            format='json'
        )
        order_data = order_response.data.get('order', order_response.data)
        order_id = order_data['id']
        
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, OrderStatus.REQUESTED)
        
        # Step 2: Provider approves order
        approve_response = self.provider_client.post(
            f'/api/v1/marketplace/orders/{order_id}/approve/',
            format='json'
        )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        
        # Verify order is approved and fulfilled
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.FULFILLED)
        self.assertEqual(order.approved_by, self.provider_user)
        self.assertIsNotNone(order.approved_at)
        self.assertIsNotNone(order.fulfilled_at)
        
        # Verify entitlement is created
        entitlement = Entitlement.objects.filter(order=order).first()
        self.assertIsNotNone(entitlement, "Entitlement should be created when order is approved")
        self.assertEqual(entitlement.status, EntitlementStatus.ACTIVE)
        self.assertEqual(entitlement.tenant, self.consumer_tenant)
        self.assertEqual(entitlement.asset, self.asset)
        self.assertEqual(entitlement.listing, self.listing)
    
    def test_reject_order_success(self):
        """Test rejecting an order (provider side)"""
        # Step 1: Consumer creates order
        order_response = self.consumer_client.post(
            '/api/v1/marketplace/orders/',
            {'listing_id': str(self.listing.id)},
            format='json'
        )
        order_data = order_response.data.get('order', order_response.data)
        order_id = order_data['id']
        
        order = Order.objects.get(id=order_id)
        self.assertEqual(order.status, OrderStatus.REQUESTED)
        
        # Step 2: Provider rejects order
        reject_response = self.provider_client.post(
            f'/api/v1/marketplace/orders/{order_id}/reject/',
            {
                'reason': 'Not suitable for our use case'
            },
            format='json'
        )
        self.assertEqual(reject_response.status_code, status.HTTP_200_OK)
        
        # Verify order is rejected
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.REJECTED)
        
        # Verify no entitlement is created
        entitlement = Entitlement.objects.filter(order=order).first()
        self.assertIsNone(entitlement)
    
    def test_purchase_free_listing_auto_approval(self):
        """Test that free listings are auto-approved"""
        # Create a new asset for this test (to avoid unique constraint violation)
        free_asset = Asset.objects.create(
            tenant=self.provider_tenant,
            key="free-asset",
            name="Free Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.provider_user
        )
        
        # Create free listing with auto-approval
        free_listing = Listing.objects.create(
            tenant=self.provider_tenant,
            asset=free_asset,
            pricing_model=PricingModel.FREE_AUTO_APPROVE,
            status=ListingStatus.PUBLISHED,
            metadata_json={
                'title': 'Free Asset',
                'short_description': 'Free dataset',
                'price_amount': 0.0
            }
        )
        
        # Consumer creates order
        order_response = self.consumer_client.post(
            '/api/v1/marketplace/orders/',
            {'listing_id': str(free_listing.id)},
            format='json'
        )
        self.assertEqual(order_response.status_code, status.HTTP_201_CREATED)
        
        order_data = order_response.data.get('order', order_response.data)
        order_id = order_data['id']
        
        # For free listings, order should be auto-approved and fulfilled
        order = Order.objects.get(id=order_id)
        # Order should be FULFILLED after auto-approval
        self.assertEqual(order.status, OrderStatus.FULFILLED)
        
        # Verify entitlement is created
        entitlement = Entitlement.objects.filter(order=order).first()
        self.assertIsNotNone(entitlement, "Entitlement should be created for auto-approved order")
        self.assertEqual(entitlement.status, EntitlementStatus.ACTIVE)
        self.assertEqual(entitlement.tenant, self.consumer_tenant)
        self.assertEqual(entitlement.asset, free_asset)
        self.assertEqual(entitlement.listing, free_listing)
        
        # Verify response includes entitlement data
        if 'entitlement' in order_response.data:
            entitlement_data = order_response.data['entitlement']
            self.assertEqual(entitlement_data['status'], EntitlementStatus.ACTIVE)
    
    def test_purchase_own_listing_fails(self):
        """Test that provider cannot purchase their own listing"""
        # Provider tries to purchase their own listing
        order_response = self.provider_client.post(
            '/api/v1/marketplace/orders/',
            {'listing_id': str(self.listing.id)},
            format='json'
        )
        
        # Should fail with appropriate error
        self.assertIn(order_response.status_code, [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN
        ])
        if order_response.status_code != status.HTTP_201_CREATED:
            error_message = str(order_response.data).lower()
            self.assertTrue(
                'own' in error_message or
                'provider' in error_message or
                'cannot' in error_message
            )


class MarketplaceEntitlementUseCasesTest(E2ETestBase):
    """Test marketplace entitlement use cases: grant, revoke, check status"""
    
    def setUp(self):
        """Set up test fixtures with provider and consumer tenants"""
        super().setUp()
        
        # Provider tenant (seller)
        self.provider_tenant = Tenant.objects.create(
            name="Provider Tenant",
            slug="provider-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.provider_user = User.objects.create_user(
            email="provider@example.com",
            password="testpass123",
            tenant=self.provider_tenant
        )
        
        self.provider_client = APIClient()
        self.provider_client.force_authenticate(user=self.provider_user)
        
        # Consumer tenant (buyer)
        self.consumer_tenant = Tenant.objects.create(
            name="Consumer Tenant",
            slug="consumer-tenant",
            kyc_status=KYCStatus.VERIFIED
        )
        
        self.consumer_user = User.objects.create_user(
            email="consumer@example.com",
            password="testpass123",
            tenant=self.consumer_tenant
        )
        
        self.consumer_client = APIClient()
        self.consumer_client.force_authenticate(user=self.consumer_user)
        
        # Create active asset and published listing
        self.asset = Asset.objects.create(
            tenant=self.provider_tenant,
            key="entitlement-asset",
            name="Entitlement Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.provider_user
        )
        
        self.listing = Listing.objects.create(
            tenant=self.provider_tenant,
            asset=self.asset,
            pricing_model=PricingModel.REQUEST_APPROVAL,
            status=ListingStatus.PUBLISHED,
            metadata_json={
                'title': 'Entitlement Asset',
                'short_description': 'A valuable dataset',
                'price_amount': 99.99,
                'currency': 'USD'
            }
        )
        
        # Create order and entitlement for tests
        self.order = Order.objects.create(
            tenant=self.consumer_tenant,
            listing=self.listing,
            created_by=self.consumer_user,
            status=OrderStatus.APPROVED,
            approved_by=self.provider_user,
            approved_at=timezone.now()
        )
        
        self.entitlement = Entitlement.objects.create(
            tenant=self.consumer_tenant,
            listing=self.listing,
            asset=self.asset,
            order=self.order,
            status=EntitlementStatus.ACTIVE
        )
    
    def test_grant_entitlement_via_order_approval(self):
        """Test that entitlement is granted when order is approved"""
        # Create a new order
        order = Order.objects.create(
            tenant=self.consumer_tenant,
            listing=self.listing,
            created_by=self.consumer_user,
            status=OrderStatus.REQUESTED
        )
        
        # Provider approves order
        approve_response = self.provider_client.post(
            f'/api/v1/marketplace/orders/{order.id}/approve/',
            format='json'
        )
        self.assertEqual(approve_response.status_code, status.HTTP_200_OK)
        
        # Verify order is fulfilled
        order.refresh_from_db()
        self.assertEqual(order.status, OrderStatus.FULFILLED)
        self.assertEqual(order.approved_by, self.provider_user)
        self.assertIsNotNone(order.approved_at)
        self.assertIsNotNone(order.fulfilled_at)
        
        # Verify entitlement is created
        entitlement = Entitlement.objects.filter(order=order).first()
        self.assertIsNotNone(entitlement, "Entitlement should be created when order is approved")
        self.assertEqual(entitlement.status, EntitlementStatus.ACTIVE)
        self.assertEqual(entitlement.tenant, self.consumer_tenant)
        self.assertEqual(entitlement.asset, self.asset)
        self.assertEqual(entitlement.listing, self.listing)
    
    def test_revoke_entitlement_success(self):
        """Test revoking an entitlement (provider side)"""
        # Verify entitlement is active
        self.assertEqual(self.entitlement.status, EntitlementStatus.ACTIVE)
        
        # Provider revokes entitlement
        revoke_response = self.provider_client.post(
            f'/api/v1/marketplace/entitlements/{self.entitlement.id}/revoke/',
            {'reason': 'Violation of terms of service'},
            format='json'
        )
        self.assertEqual(revoke_response.status_code, status.HTTP_200_OK)
        
        # Verify entitlement is revoked
        self.entitlement.refresh_from_db()
        self.assertEqual(self.entitlement.status, EntitlementStatus.REVOKED)
        self.assertIsNotNone(self.entitlement.revoked_at)
        if self.entitlement.metadata_json:
            self.assertIn('revocation_reason', self.entitlement.metadata_json)
    
    def test_check_entitlement_status_success(self):
        """Test checking entitlement status"""
        # Consumer checks their entitlements
        entitlements_response = self.consumer_client.get(
            '/api/v1/marketplace/entitlements/'
        )
        self.assertEqual(entitlements_response.status_code, status.HTTP_200_OK)
        
        # Verify entitlement is in the list
        results = entitlements_response.data.get('results', entitlements_response.data)
        if isinstance(results, list):
            entitlement_ids = [e.get('id') for e in results if isinstance(e, dict)]
            self.assertIn(str(self.entitlement.id), entitlement_ids)
        
        # Check specific entitlement
        detail_response = self.consumer_client.get(
            f'/api/v1/marketplace/entitlements/{self.entitlement.id}/'
        )
        self.assertEqual(detail_response.status_code, status.HTTP_200_OK)
        self.assertEqual(detail_response.data['id'], str(self.entitlement.id))
        self.assertEqual(detail_response.data['status'], EntitlementStatus.ACTIVE)
    
    def test_check_access_via_entitlement(self):
        """Test checking access to asset via entitlement"""
        # Consumer checks access to asset
        check_response = self.consumer_client.post(
            '/api/v1/marketplace/entitlements/check-access/',
            {'asset_id': str(self.asset.id)},
            format='json'
        )
        self.assertEqual(check_response.status_code, status.HTTP_200_OK)
        self.assertTrue(check_response.data['has_access'])
        self.assertEqual(check_response.data['entitlement_id'], str(self.entitlement.id))
    
    def test_check_access_without_entitlement_fails(self):
        """Test that checking access without entitlement returns False"""
        # Create another asset without entitlement
        other_asset = Asset.objects.create(
            tenant=self.provider_tenant,
            key="other-asset",
            name="Other Asset",
            status=AssetStatus.ACTIVE,
            created_by=self.provider_user
        )
        
        # Consumer checks access to asset they don't have entitlement for
        check_response = self.consumer_client.post(
            '/api/v1/marketplace/entitlements/check-access/',
            {'asset_id': str(other_asset.id)},
            format='json'
        )
        self.assertEqual(check_response.status_code, status.HTTP_200_OK)
        self.assertFalse(check_response.data['has_access'])
        self.assertIsNone(check_response.data['entitlement_id'])
    
    def test_revoke_entitlement_by_non_provider_fails(self):
        """Test that only provider can revoke entitlements"""
        # Consumer tries to revoke entitlement (should fail)
        revoke_response = self.consumer_client.post(
            f'/api/v1/marketplace/entitlements/{self.entitlement.id}/revoke/',
            {'reason': 'Test'},
            format='json'
        )
        
        # Should fail with 403 Forbidden
        self.assertEqual(revoke_response.status_code, status.HTTP_403_FORBIDDEN)
        
        # Verify entitlement is still active
        self.entitlement.refresh_from_db()
        self.assertEqual(self.entitlement.status, EntitlementStatus.ACTIVE)
    
    def test_list_entitlements_with_filters(self):
        """Test listing entitlements with filters"""
        # List all entitlements
        all_response = self.consumer_client.get('/api/v1/marketplace/entitlements/')
        self.assertEqual(all_response.status_code, status.HTTP_200_OK)
        
        # Filter by status
        active_response = self.consumer_client.get(
            '/api/v1/marketplace/entitlements/',
            {'status': EntitlementStatus.ACTIVE}
        )
        self.assertEqual(active_response.status_code, status.HTTP_200_OK)
        
        # Filter by asset_id
        asset_response = self.consumer_client.get(
            '/api/v1/marketplace/entitlements/',
            {'asset_id': str(self.asset.id)}
        )
        self.assertEqual(asset_response.status_code, status.HTTP_200_OK)
        
        # Filter by order_id
        order_response = self.consumer_client.get(
            '/api/v1/marketplace/entitlements/',
            {'order_id': str(self.order.id)}
        )
        self.assertEqual(order_response.status_code, status.HTTP_200_OK)

