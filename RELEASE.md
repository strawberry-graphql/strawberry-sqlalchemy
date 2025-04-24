Release type: enhancement


**Added support for GraphQL directives** in the SQLAlchemy type mapper, enabling better integration with GraphQL federation.
  
  **Example usage:**
  ```python
  @mapper.type(Employee, directives=["@deprecated(reason: 'Use newEmployee instead')"])
  class Employee:
      pass
