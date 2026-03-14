NODE_TABLE_SCHEMAS = {
    "Repository": """
        CREATE NODE TABLE Repository(
          id STRING,
          name STRING,
          repo_path STRING,
          indexed_at STRING,
          index_version STRING,
          PRIMARY KEY (id)
        );
    """,
    "Folder": """
        CREATE NODE TABLE Folder(
          id STRING,
          repo_id STRING,
          name STRING,
          file_path STRING,
          PRIMARY KEY (id)
        );
    """,
    "File": """
        CREATE NODE TABLE File(
          id STRING,
          repo_id STRING,
          name STRING,
          file_path STRING,
          language STRING,
          is_test BOOLEAN,
          PRIMARY KEY (id)
        );
    """,
    "Function": """
        CREATE NODE TABLE Function(
          id STRING,
          repo_id STRING,
          name STRING,
          file_path STRING,
          language STRING,
          start_line INT64,
          end_line INT64,
          signature STRING,
          visibility STRING,
          is_exported BOOLEAN,
          PRIMARY KEY (id)
        );
    """,
    "Method": """
        CREATE NODE TABLE Method(
          id STRING,
          repo_id STRING,
          name STRING,
          owner_name STRING,
          file_path STRING,
          language STRING,
          start_line INT64,
          end_line INT64,
          signature STRING,
          visibility STRING,
          is_exported BOOLEAN,
          PRIMARY KEY (id)
        );
    """,
    "Class": """
        CREATE NODE TABLE Class(
          id STRING,
          repo_id STRING,
          name STRING,
          file_path STRING,
          language STRING,
          start_line INT64,
          end_line INT64,
          visibility STRING,
          is_exported BOOLEAN,
          PRIMARY KEY (id)
        );
    """,
    "Interface": """
        CREATE NODE TABLE Interface(
          id STRING,
          repo_id STRING,
          name STRING,
          file_path STRING,
          language STRING,
          start_line INT64,
          end_line INT64,
          visibility STRING,
          is_exported BOOLEAN,
          PRIMARY KEY (id)
        );
    """,
    "ModuleSkill": """
        CREATE NODE TABLE ModuleSkill(
          id STRING,
          repo_id STRING,
          name STRING,
          label STRING,
          summary STRING,
          generated_at STRING,
          file_count INT64,
          symbol_count INT64,
          entry_point_count INT64,
          flow_count INT64,
          PRIMARY KEY (id)
        );
    """,
}

REL_TABLE_SCHEMA = """
    CREATE REL TABLE CodeRelation(
      FROM Repository TO Folder,
      FROM Folder TO Folder,
      FROM Folder TO File,
      FROM File TO File,
      FROM File TO Function,
      FROM File TO Method,
      FROM File TO Class,
      FROM File TO Interface,
      FROM Class TO Method,
      FROM Function TO Function,
      FROM Function TO Method,
      FROM Function TO Class,
      FROM Method TO Function,
      FROM Method TO Method,
      FROM Method TO Class,
      FROM File TO ModuleSkill,
      FROM Function TO ModuleSkill,
      FROM Method TO ModuleSkill,
      FROM Class TO ModuleSkill,
      FROM Interface TO ModuleSkill,
      FROM ModuleSkill TO ModuleSkill,
      type STRING,
      confidence DOUBLE,
      reason STRING,
      step INT64
    );
"""
