"""
Unit tests for ODPS error handling in CLI.

Tests verify:
1. Error parsing from API responses
2. Parameter validation
3. User-friendly error messages
4. Error context and suggestions
"""

import json

import pytest
from datahub_cli.odps_errors import (
    ODPSCLIError,
    ODPSExportError,
    ODPSLinkingError,
    ODPSNormalizationError,
    ODPSParameterError,
    ODPSRefResolutionError,
    ODPSValidationError,
    handle_api_error,
    parse_api_error_response,
    validate_contract_id,
    validate_file_format,
    validate_mutually_exclusive_options,
    validate_odcs_version,
    validate_odps_version,
    validate_required_option,
)


class TestODPSCLIError:
    """Test base ODPSCLIError class"""

    def test_odps_cli_error_basic(self):
        """Test basic ODPSCLIError creation"""
        error = ODPSCLIError("Test error message")
        assert str(error) == "Test error message"
        assert error.error_code == "ODPS_CLI_ERROR"
        assert error.context == {}
        assert error.suggestion is None

    def test_odps_cli_error_with_context(self):
        """Test ODPSCLIError with context"""
        error = ODPSCLIError(
            "Test error",
            error_code="TEST_ERROR",
            context={"field_path": "/product/name", "file_path": "test.json"},
            suggestion="Fix the field",
        )
        assert error.error_code == "TEST_ERROR"
        assert error.context["field_path"] == "/product/name"
        assert error.suggestion == "Fix the field"

    def test_odps_cli_error_format_message(self):
        """Test error message formatting"""
        error = ODPSCLIError(
            "Validation failed",
            context={"field_path": "/product/name", "expected": "string", "actual": "number"},
            suggestion="Change the field type",
        )
        message = error.format_message()
        assert "Validation failed" in message
        assert "Field: /product/name" in message
        assert "Expected: string" in message
        assert "Actual: number" in message
        assert "Suggestion: Change the field type" in message


class TestODPSErrorTypes:
    """Test specific ODPS error types"""

    def test_odps_validation_error(self):
        """Test ODPSValidationError"""
        error = ODPSValidationError(
            "Schema validation failed",
            error_code="SCHEMA_VALIDATION_FAILED",
            context={"field_path": "/product/version"},
        )
        assert isinstance(error, ODPSCLIError)
        assert error.error_code == "SCHEMA_VALIDATION_FAILED"

    def test_odps_ref_resolution_error(self):
        """Test ODPSRefResolutionError"""
        error = ODPSRefResolutionError(
            "Reference resolution failed",
            error_code="RESOLUTION_FAILED",
            context={"ref_path": "#/definitions/Product"},
        )
        assert isinstance(error, ODPSCLIError)
        assert error.error_code == "RESOLUTION_FAILED"

    def test_odps_normalization_error(self):
        """Test ODPSNormalizationError"""
        error = ODPSNormalizationError(
            "Normalization failed",
            error_code="NORMALIZATION_FAILED",
            context={"field_path": "/product/name"},
        )
        assert isinstance(error, ODPSCLIError)
        assert error.error_code == "NORMALIZATION_FAILED"

    def test_odps_export_error(self):
        """Test ODPSExportError"""
        error = ODPSExportError(
            "Export failed", error_code="EXPORT_FAILED", context={"export_format": "yaml"}
        )
        assert isinstance(error, ODPSCLIError)
        assert error.error_code == "EXPORT_FAILED"

    def test_odps_linking_error(self):
        """Test ODPSLinkingError"""
        error = ODPSLinkingError(
            "Linking failed",
            error_code="LINKING_FAILED",
            context={"odcs_id": "odcs-1", "odps_id": "odps-1"},
        )
        assert isinstance(error, ODPSCLIError)
        assert error.error_code == "LINKING_FAILED"

    def test_odps_parameter_error(self):
        """Test ODPSParameterError"""
        error = ODPSParameterError(
            "Invalid parameter", error_code="INVALID_PARAMETER", context={"parameter": "version"}
        )
        assert isinstance(error, ODPSCLIError)
        assert error.error_code == "INVALID_PARAMETER"


class TestParseAPIErrorResponse:
    """Test parsing API error responses"""

    def test_parse_validation_error(self):
        """Test parsing validation error response"""
        error_data = {
            "error": {
                "code": "SCHEMA_VALIDATION_FAILED",
                "message": "Schema validation failed",
                "context": {
                    "field_path": "/product/version",
                    "expected": "string",
                    "actual": "number",
                },
            }
        }
        error = parse_api_error_response(error_data)
        assert isinstance(error, ODPSValidationError)
        assert error.error_code == "SCHEMA_VALIDATION_FAILED"
        assert error.context["field_path"] == "/product/version"

    def test_parse_ref_resolution_error(self):
        """Test parsing ref resolution error response"""
        error_data = {
            "error": {
                "code": "RESOLUTION_FAILED",
                "message": "Reference resolution failed",
                "context": {"ref_path": "#/definitions/Product", "ref_type": "internal"},
            }
        }
        error = parse_api_error_response(error_data)
        assert isinstance(error, ODPSRefResolutionError)
        assert error.error_code == "RESOLUTION_FAILED"

    def test_parse_normalization_error(self):
        """Test parsing normalization error response"""
        error_data = {
            "error": {
                "code": "NORMALIZATION_FAILED",
                "message": "Normalization failed",
                "context": {
                    "field_path": "/product/name",
                    "source_path": "/product/name",
                    "target_path": "/name",
                },
            }
        }
        error = parse_api_error_response(error_data)
        assert isinstance(error, ODPSNormalizationError)
        assert error.error_code == "NORMALIZATION_FAILED"

    def test_parse_export_error(self):
        """Test parsing export error response"""
        error_data = {
            "error": {
                "code": "EXPORT_FAILED",
                "message": "Export failed",
                "context": {"export_format": "yaml", "file_path": "/tmp/export.yaml"},
            }
        }
        error = parse_api_error_response(error_data)
        assert isinstance(error, ODPSExportError)
        assert error.error_code == "EXPORT_FAILED"

    def test_parse_linking_error(self):
        """Test parsing linking error response"""
        error_data = {
            "error": {
                "code": "LINKING_FAILED",
                "message": "Linking failed",
                "context": {"source_id": "odcs-1", "target_id": "odps-1"},
            }
        }
        error = parse_api_error_response(error_data)
        assert isinstance(error, ODPSLinkingError)
        assert error.error_code == "LINKING_FAILED"

    def test_parse_generic_error(self):
        """Test parsing generic error response"""
        error_data = {"error": {"code": "UNKNOWN_ERROR", "message": "Unknown error occurred"}}
        error = parse_api_error_response(error_data)
        assert isinstance(error, ODPSCLIError)
        assert error.error_code == "UNKNOWN_ERROR"

    def test_parse_error_with_string_error(self):
        """Test parsing error with string error field"""
        error_data = {"error": "Simple error message"}
        error = parse_api_error_response(error_data)
        assert isinstance(error, ODPSCLIError)
        assert "Simple error message" in error.message

    def test_parse_error_invalid_data(self):
        """Test parsing invalid error data"""
        # Type checker will complain, but we test runtime behavior
        error = parse_api_error_response({})  # Empty dict should return None or generic error
        # parse_api_error_response expects Dict, so passing non-dict would fail type check
        # But at runtime, if we somehow get non-dict, it returns None
        assert error is None or isinstance(error, ODPSCLIError)


class TestHandleAPIError:
    """Test handling API errors"""

    def test_handle_json_error(self):
        """Test handling JSON error response"""
        error_json = json.dumps(
            {
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message": "Validation failed",
                    "context": {"field_path": "/product/name"},
                }
            }
        )
        error = handle_api_error(error_json, 400, "contracts/products/")
        assert isinstance(error, ODPSCLIError)
        assert error.context["status_code"] == 400
        assert error.context["endpoint"] == "contracts/products/"

    def test_handle_text_error(self):
        """Test handling text error response"""
        error = handle_api_error("Simple error text", 500)
        assert isinstance(error, ODPSCLIError)
        assert error.context["status_code"] == 500

    def test_handle_http_400(self):
        """Test handling HTTP 400 error"""
        error = handle_api_error('{"error": {"message": "Bad request"}}', 400)
        assert error.suggestion is not None
        assert "parameters" in error.suggestion.lower()

    def test_handle_http_401(self):
        """Test handling HTTP 401 error"""
        error = handle_api_error('{"error": {"message": "Unauthorized"}}', 401)
        assert error.suggestion is not None
        assert "login" in error.suggestion.lower() or "authenticate" in error.suggestion.lower()

    def test_handle_http_404(self):
        """Test handling HTTP 404 error"""
        error = handle_api_error(
            '{"error": {"message": "Not found"}}', 404, "contracts/contracts/123/"
        )
        assert error.suggestion is not None
        assert "not found" in error.suggestion.lower() or "id" in error.suggestion.lower()


class TestValidateODPSVersion:
    """Test ODPS version validation"""

    def test_validate_valid_version(self):
        """Test validating valid ODPS version"""
        validate_odps_version("4.1")
        validate_odps_version("4.0")
        validate_odps_version("3.2")

    def test_validate_invalid_version_format(self):
        """Test validating invalid version format"""
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_odps_version("4")
        assert "Invalid ODPS version format" in str(exc_info.value)
        assert exc_info.value.suggestion is not None

    def test_validate_invalid_version_with_letters(self):
        """Test validating version with letters"""
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_odps_version("4.1a")
        assert "Invalid ODPS version format" in str(exc_info.value)

    def test_validate_none_version(self):
        """Test validating None version (should pass)"""
        validate_odps_version(None)


class TestValidateODCSVersion:
    """Test ODCS version validation"""

    def test_validate_valid_version(self):
        """Test validating valid ODCS version"""
        validate_odcs_version("3.0.2")
        validate_odcs_version("3.0.1")
        validate_odcs_version("3.0.0")
        validate_odcs_version("3.0.0-preview")
        validate_odcs_version("2.2.2")

    def test_validate_invalid_version_format_missing_minor(self):
        """Test validating invalid version format - missing minor"""
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_odcs_version("3")
        assert "Invalid ODCS version format" in str(exc_info.value)
        assert exc_info.value.suggestion is not None

    def test_validate_invalid_version_format_with_letters(self):
        """Test validating version with invalid letters"""
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_odcs_version("3.0.2a")
        assert "Invalid ODCS version format" in str(exc_info.value)

    def test_validate_unsupported_version(self):
        """Test validating unsupported ODCS version"""
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_odcs_version("99.99.99")
        assert "not supported" in str(exc_info.value).lower()
        assert "3.0.2" in str(exc_info.value)  # Should mention supported versions

    def test_validate_none_version(self):
        """Test validating None version (should pass)"""
        validate_odcs_version(None)

    def test_validate_version_with_suffix(self):
        """Test validating version with suffix"""
        validate_odcs_version("3.0.0-preview")

    def test_validate_version_with_patch(self):
        """Test validating version with patch number"""
        validate_odcs_version("3.0.2")
        validate_odcs_version("2.2.2")

    def test_validate_version_without_patch(self):
        """Test validating version without patch number"""
        validate_odcs_version("3.0.0")
        validate_odcs_version("3.0.1")

    def test_validate_invalid_suffix_format(self):
        """Test validating version with invalid suffix format"""
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_odcs_version("3.0.0_preview")  # Underscore instead of dash
        assert "Invalid ODCS version format" in str(exc_info.value)

    def test_validate_non_string_version(self):
        """Test validating non-string version"""
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_odcs_version(3.0)  # type: ignore
        assert "must be a string" in str(exc_info.value).lower()


class TestValidateContractID:
    """Test contract ID validation"""

    def test_validate_valid_id(self):
        """Test validating valid contract ID"""
        validate_contract_id("contract-123")
        validate_contract_id("odcs-456")
        validate_contract_id("odps-789")

    def test_validate_empty_id(self):
        """Test validating empty contract ID"""
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_contract_id("")
        assert "cannot be empty" in str(exc_info.value).lower()

    def test_validate_whitespace_id(self):
        """Test validating contract ID with whitespace"""
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_contract_id("  contract-123  ")
        assert "whitespace" in str(exc_info.value).lower()

    def test_validate_id_with_type(self):
        """Test validating contract ID with type"""
        validate_contract_id("odcs-123", "odcs")
        validate_contract_id("odps-456", "odps")


class TestValidateFileFormat:
    """Test file format validation"""

    def test_validate_json_file(self, tmp_path):
        """Test validating JSON file"""
        file_path = tmp_path / "test.json"
        file_path.write_text('{"test": "data"}')
        format_type = validate_file_format(str(file_path))
        assert format_type == "JSON"

    def test_validate_yaml_file(self, tmp_path):
        """Test validating YAML file"""
        file_path = tmp_path / "test.yaml"
        file_path.write_text("test: data")
        format_type = validate_file_format(str(file_path))
        assert format_type == "YAML"

    def test_validate_yml_file(self, tmp_path):
        """Test validating .yml file"""
        file_path = tmp_path / "test.yml"
        file_path.write_text("test: data")
        format_type = validate_file_format(str(file_path))
        assert format_type == "YAML"

    def test_validate_file_without_extension(self, tmp_path):
        """Test validating file without extension"""
        file_path = tmp_path / "test"
        file_path.write_text('{"test": "data"}')
        format_type = validate_file_format(str(file_path))
        assert format_type == "JSON"

    def test_validate_nonexistent_file(self):
        """Test validating nonexistent file"""
        # File with extension should still try to validate format
        # But if file doesn't exist and we need to read it, should raise error
        # For files without extension, we need to read to detect format
        import os
        import tempfile

        with tempfile.TemporaryDirectory() as tmpdir:
            nonexistent = os.path.join(tmpdir, "nonexistent")
            with pytest.raises(ODPSParameterError) as exc_info:
                validate_file_format(nonexistent)  # No extension, needs to read
            assert (
                "not found" in str(exc_info.value).lower()
                or "read" in str(exc_info.value).lower()
                or "exist" in str(exc_info.value).lower()
            )

    def test_validate_file_with_allowed_formats(self, tmp_path):
        """Test validating file with allowed formats"""
        file_path = tmp_path / "test.json"
        file_path.write_text('{"test": "data"}')
        format_type = validate_file_format(str(file_path), allowed_formats=["JSON", "YAML"])
        assert format_type == "JSON"

    def test_validate_file_unsupported_format(self, tmp_path):
        """Test validating file with unsupported format"""
        file_path = tmp_path / "test.xml"
        file_path.write_text("<test>data</test>")
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_file_format(str(file_path), allowed_formats=["JSON", "YAML"])
        assert "unsupported" in str(exc_info.value).lower()


class TestValidateMutuallyExclusiveOptions:
    """Test mutually exclusive options validation"""

    def test_validate_mutually_exclusive_both_provided(self):
        """Test validating when both options are provided"""
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_mutually_exclusive_options("extract-odcs", True, "link-odcs", "odcs-123")
        assert "Cannot use both" in str(exc_info.value)
        assert "extract-odcs" in str(exc_info.value)
        assert "link-odcs" in str(exc_info.value)

    def test_validate_mutually_exclusive_none_provided(self):
        """Test validating when neither option is provided (should pass)"""
        validate_mutually_exclusive_options("extract-odcs", False, "link-odcs", None)

    def test_validate_mutually_exclusive_one_provided(self):
        """Test validating when one option is provided (should pass)"""
        validate_mutually_exclusive_options("extract-odcs", True, "link-odcs", None)
        validate_mutually_exclusive_options("extract-odcs", False, "link-odcs", "odcs-123")


class TestValidateRequiredOption:
    """Test required option validation"""

    def test_validate_required_option_provided(self):
        """Test validating when required option is provided (should pass)"""
        validate_required_option("extract-odcs", True)

    def test_validate_required_option_missing(self):
        """Test validating when required option is missing"""
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_required_option("extract-odcs", False)
        assert "Required option" in str(exc_info.value) or "Must specify" in str(exc_info.value)
        assert "extract-odcs" in str(exc_info.value)

    def test_validate_required_option_with_alternative(self):
        """Test validating required option with alternative"""
        with pytest.raises(ODPSParameterError) as exc_info:
            validate_required_option("extract-odcs", False, alternative="link-odcs")
        assert "Must specify either" in str(exc_info.value)
        assert "extract-odcs" in str(exc_info.value)
        assert "link-odcs" in str(exc_info.value)
