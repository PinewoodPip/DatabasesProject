
from dataclasses import dataclass, field, asdict

@dataclass
class Entity:
    def serialize_type(obj):
        serializable_types = set([dict, list])
        serialized_obj = obj
        if type(obj) in serializable_types:
            serialized_obj = obj
        elif type(obj) == set:
            serialized_obj = list(obj)
        elif obj is Entity:
            serialized_obj = Entity.serialize_type(obj)
        return serialized_obj
    
    def dict(self):
        return {k: Entity.serialize_type(v) for k, v in asdict(self).items()}
