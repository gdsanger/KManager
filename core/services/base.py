"""
Base service exceptions and utilities
"""


class ServiceError(Exception):
    """Base exception for service errors"""
    pass


class ServiceNotConfigured(ServiceError):
    """Service is not properly configured"""
    pass


class ServiceDisabled(ServiceError):
    """Service is disabled"""
    pass


class ServiceUnavailable(ServiceError):
    """Service is temporarily unavailable"""
    pass
