# ODPS (Open Data Product Standard) CLI Command Reference

> **Canonical guide:** [../../sdk/python/docs/ODPS_USAGE.md](../../sdk/python/docs/ODPS_USAGE.md)
> (concepts, SDK code, and setup — this file keeps ONLY the CLI command
> examples; W6.4 dedupe of the diverging `cli/docs` vs `sdk/python/docs`
> copies).

### Product-First Flow
```bash
# Create ODPS product with embedded ODCS contract
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs

# With asset ID
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs \
  --asset-id <asset-id>

# From YAML file
datahub contracts create-odps \
  --file product.odps.yaml \
  --extract-odcs
```

### Link Flow
```bash
# Create ODPS and link to existing ODCS contract
datahub contracts create-odps \
  --file product.odps.json \
  --link-odcs <odcs-contract-id>
```

### Link ODPS to ODCS
```bash
# Link existing ODPS contract to existing ODCS contract
datahub contracts link-odps <odcs-contract-id> <odps-contract-id>
```

### Unlink ODPS from ODCS
```bash
# Unlink ODPS contract from ODCS contract
datahub contracts unlink-odps <odcs-contract-id>
```

### List Contract Links
```bash
# View all links for a contract
datahub contracts list-links <contract-id>

# Output shows:
# - ODPS Link: <odps-contract-id> (if contract is ODCS)
# - ODCS Link: <odcs-contract-id> (if contract is ODPS)
```

### Get Contract with ODPS Information
```bash
# Get contract with ODPS information
datahub contracts get <odps-contract-id> --show-odps

# Output includes:
# - Basic contract information
# - ODPS Information section:
#   - Pricing Plans (count, details)
#   - Access Methods (count, details)
#   - Payment Gateways (if configured)
```

### Get Pricing Plans
```bash
# Get pricing plans (table format)
datahub contracts get-pricing <odps-contract-id>

# Get pricing plans (JSON format)
datahub contracts get-pricing <odps-contract-id> --format json
```

### Get Access Methods
```bash
# Get access methods (table format)
datahub contracts get-access-methods <odps-contract-id>

# Get access methods (JSON format)
datahub contracts get-access-methods <odps-contract-id> --format json
```

### Export ODPS Contract
```bash
# Export as ODPS JSON
datahub contracts export <contract-id> \
  --format odps \
  --output-format json

# Export as ODPS YAML
datahub contracts export <contract-id> \
  --format odps \
  --output-format yaml

# Export with specific ODPS version
datahub contracts export <contract-id> \
  --format odps \
  --output-format json \
  --version 4.1
```

### Download ODPS Contract
```bash
# Download as ODPS JSON file
datahub contracts download <contract-id> \
  --format odps \
  --output-format json \
  --output product.odps.json

# Download as ODPS YAML file
datahub contracts download <contract-id> \
  --format odps \
  --output-format yaml \
  --output product.odps.yaml
```

### Pattern 1: Product-First Workflow
```bash
# 1. Create ODPS product with embedded ODCS contract
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs \
  --asset-id <asset-id>

# Output:
# ODPS Contract: <odps-id>
# ODCS Contract: <odcs-id>

# 2. View ODPS marketplace information
datahub contracts get <odps-id> --show-odps

# 3. Get pricing details
datahub contracts get-pricing <odps-id>

# 4. Get access methods
datahub contracts get-access-methods <odps-id>
```

### Pattern 2: Link Workflow
```bash
# 1. Create ODCS contract (technical specification)
datahub contracts create --file technical-spec.odcs.yaml

# 2. Create ODPS contract and link to ODCS
datahub contracts create-odps \
  --file marketplace-product.odps.json \
  --link-odcs <odcs-contract-id>

# 3. Verify the link
datahub contracts list-links <odcs-contract-id>

# 4. View marketplace information
datahub contracts get <odps-contract-id> --show-odps
```

### Pattern 3: Manual Linking
```bash
# 1. Create ODCS contract
datahub contracts create --file technical.odcs.yaml

# 2. Create ODPS contract (without linking)
datahub contracts create-odps \
  --file product.odps.json \
  --link-odcs <temporary-odcs-id>  # Use a placeholder or skip

# 3. Manually link them
datahub contracts link-odps <odcs-id> <odps-id>

# 4. Verify link
datahub contracts list-links <odcs-id>
```

### Pattern 4: Information Retrieval Workflow
```bash
# 1. Get full ODPS information
datahub contracts get <odps-contract-id> --show-odps

# 2. Get specific pricing information
datahub contracts get-pricing <odps-contract-id> --format json

# 3. Get specific access methods
datahub contracts get-access-methods <odps-contract-id> --format json

# 4. Export for analysis
datahub contracts export <odps-contract-id> \
  --format odps \
  --output-format json \
  --cli-format json > product-analysis.json
```

#### Issue: "CSRF verification failed" when creating ODPS contracts
```bash
datahub config set api_key your-api-key-here
```

#### Issue: "Could not extract contract ID from output"
```bash
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs \
  --output-format json
```

#### Issue: "No pricing plans found"
```bash
datahub contracts get <contract-id>
# Look for: Spec Type: ODPS
# Look for: Normalization Status: NORMALIZED_OK
```

### Best Practices
   ```bash
   datahub contracts create-odps --file product.odps.json --extract-odcs
   ```

   ```bash
   datahub contracts get-pricing <id> --format json | jq '.pricing_plans'
   ```

   ```bash
   datahub contracts list-links <contract-id>
   ```

   ```bash
   datahub contracts export <id> --format odps --output-format json > backup.json
   ```

## Troubleshooting

### Common Issues

#### Issue: "CSRF verification failed" when creating ODPS contracts

**Solution**: Ensure you're using API key authentication:
```bash
datahub config set api_key your-api-key-here
```

#### Issue: "Could not extract contract ID from output"

**Solution**: Use JSON format to get structured output:
```bash
datahub contracts create-odps \
  --file product.odps.json \
  --extract-odcs \
  --output-format json
```

#### Issue: "No pricing plans found"

**Possible Causes**:
1. Contract is not an ODPS contract (check `original_spec_type`)
2. ODPS contract doesn't have marketplace data
3. Normalization didn't preserve pricing plans

**Solution**: Check contract type and normalization status:
```bash
datahub contracts get <contract-id>
# Look for: Spec Type: ODPS
# Look for: Normalization Status: NORMALIZED_OK
```

#### Issue: "No access methods found"

**Possible Causes**:
1. Contract is not an ODPS contract
2. ODPS contract doesn't have access methods defined
3. Access methods weren't preserved during normalization

**Solution**: Verify contract has access methods in original_raw or hub_contract_json.

### Best Practices

1. **Always specify format explicitly** when creating ODPS contracts:
   ```bash
   datahub contracts create-odps --file product.odps.json --extract-odcs
   ```

2. **Use JSON format for automation**:
   ```bash
   datahub contracts get-pricing <id> --format json | jq '.pricing_plans'
   ```

3. **Verify links after creation**:
   ```bash
   datahub contracts list-links <contract-id>
   ```

4. **Export before making changes**:
   ```bash
   datahub contracts export <id> --format odps --output-format json > backup.json
   ```
