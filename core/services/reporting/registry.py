"""
Template Registry

Manages report template registration and resolution.
No if/else logic - templates register themselves.
"""
from typing import Dict, Callable, Any


class TemplateRegistry:
    """
    Registry for report templates.
    
    Templates register themselves with a key and provide a factory function
    that returns an object with:
    - build_story(context) -> list[Flowable]
    - draw_header_footer(canvas, doc, context) (optional)
    """
    
    def __init__(self):
        self._templates: Dict[str, Callable] = {}
    
    def register(self, report_key: str, template_factory: Callable):
        """
        Register a report template.
        
        Args:
            report_key: Unique identifier for the report (e.g., 'change.v1')
            template_factory: Factory function that returns a template instance
        """
        if report_key in self._templates:
            raise ValueError(f"Template '{report_key}' is already registered")
        
        self._templates[report_key] = template_factory
    
    def get(self, report_key: str) -> Any:
        """
        Get a template instance by key.
        
        Args:
            report_key: The report key to look up
            
        Returns:
            Template instance
            
        Raises:
            KeyError: If report_key is not registered
        """
        if report_key not in self._templates:
            raise KeyError(f"Template '{report_key}' is not registered. "
                         f"Available templates: {', '.join(self._templates.keys())}")
        
        return self._templates[report_key]()
    
    def list_templates(self):
        """
        List all registered template keys.
        
        Returns:
            List of registered template keys
        """
        return list(self._templates.keys())


# Global registry instance
_registry = TemplateRegistry()


def register_template(report_key: str):
    """
    Decorator to register a report template class.
    
    Usage:
        @register_template('change.v1')
        class ChangeReportV1:
            def build_story(self, context):
                ...
    
    Args:
        report_key: Unique identifier for the report
    """
    def decorator(template_class):
        _registry.register(report_key, template_class)
        return template_class
    
    return decorator


def get_template(report_key: str):
    """
    Get a template instance by key.
    
    Args:
        report_key: The report key to look up
        
    Returns:
        Template instance
    """
    return _registry.get(report_key)


def list_templates():
    """
    List all registered template keys.
    
    Returns:
        List of registered template keys
    """
    return _registry.list_templates()
