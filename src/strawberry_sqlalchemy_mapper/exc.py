class UnsupportedColumnType(Exception):
    def __init__(self, key, type):
        super().__init__(
            f"Unsupported column type: `{type}` on column: `{key}`."
            "Possible fix: exclude this column"
        )


class UnsupportedAssociationProxyTarget(Exception):
    def __init__(self, key):
        super().__init__(
            f"Association proxy `{key}` is expected to be of form "
            "association_proxy(relationship_name, other relationship name). "
            "Ensure it matches the expected form or add this association proxy to __exclude__."
        )


class HybridPropertyNotAnnotated(Exception):
    def __init__(self, key):
        super().__init__(
            f"Descriptor `{key}` is a hybrid property, but does not have an annotated return type"
        )


class UnsupportedDescriptorType(Exception):
    def __init__(self, key):
        super().__init__(
            f"Descriptor `{key}` is expected to be a column, relationship, or association proxy."
        )


class InterfaceModelNotPolymorphic(Exception):
    def __init__(self, model):
        super().__init__(
            f"Model `{model}` is not polymorphic or is not the base model of its "
            "inheritance chain, and thus cannot be used as an interface."
        )
