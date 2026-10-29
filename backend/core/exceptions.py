from typing import Optional

class DomainException(Exception):
    def __init__(self, message: str, details: Optional[dict] = None):
        self.message = message
        self.details = details or {}
        super().__init__(self.message)

class ResourceNotFound(DomainException): pass
class ProfesorNotFound(ResourceNotFound): pass
class ActividadNotFound(ResourceNotFound): pass
class UsuarioNotFound(ResourceNotFound): pass
class AreaNotFound(ResourceNotFound): pass
class DepartamentoNotFound(ResourceNotFound): pass

class ValidationError(DomainException): pass
class DuplicateResourceError(ValidationError): pass
class InvalidStateError(ValidationError): pass
class ConstraintViolation(ValidationError): pass

class PermissionDenied(DomainException): pass
class NotYourTurn(PermissionDenied): pass
class UnauthorizedAreaAccess(PermissionDenied): pass
class UnauthorizedDepartmentAccess(PermissionDenied): pass

class OrdenacionError(DomainException): pass
class NoViableOptions(OrdenacionError): pass
class IncompleteTurn(OrdenacionError): pass
class ViabilityLost(OrdenacionError): pass
class OrdenacionFinished(OrdenacionError): pass
class ConcurrentModification(OrdenacionError): pass
class OrdenacionClosed(OrdenacionError): pass
class OrdenacionClosureInvalid(OrdenacionError): pass

class SolverError(DomainException): pass
