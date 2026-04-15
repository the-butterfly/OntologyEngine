// ontology-engine-ui/src/components/rule/TargetEntitiesEditor.tsx
// Component for selecting target entity types (L1 Schema) for a rule group

import React, { useState, useEffect } from 'react';
import { Select, Tag, Spin, message } from 'antd';
import { spaceApi } from '../../api/spaceApi';
import { caseInsensitiveFilter } from '../../utils/filterOptions';

interface TargetEntitiesEditorProps {
  schemaId: string;
  value?: string[];
  onChange?: (entities: string[]) => void;
  disabled?: boolean;
}

interface FactObjectResponse {
  id?: string;
  name?: string;
  concept?: string;
  [key: string]: unknown;
}

export default function TargetEntitiesEditor({
  schemaId,
  value = [],
  onChange,
  disabled = false,
}: TargetEntitiesEditorProps) {
  const [entities, setEntities] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!schemaId) return;

    const fetchEntities = async () => {
      setLoading(true);
      try {
        const data = await spaceApi.listFactObjects(schemaId);
        const entityNames = data.map((item: FactObjectResponse) => {
          if (typeof item === 'string') return item;
          if (item.name) return item.name;
          if (item.concept) return item.concept;
          if (item.id) return item.id;
          return String(item);
        });
        setEntities(entityNames);
      } catch (error) {
        console.error('Failed to fetch L1 entities:', error);
        message.error('Failed to load entity types');
        setEntities([]);
      } finally {
        setLoading(false);
      }
    };

    fetchEntities();
  }, [schemaId]);

  const handleChange = (newValues: string[]) => {
    onChange?.(newValues);
  };

  const tagRender = (props: {
    label?: React.ReactNode;
    closable: boolean;
    onClose: () => void;
  }) => {
    const { label, closable, onClose } = props;
    return (
      <Tag closable={closable} onClose={onClose} style={{ marginRight: 4 }}>
        {label}
      </Tag>
    );
  };

  if (loading) {
    return <Spin size="small" />;
  }

  return (
    <Select
      mode="multiple"
      placeholder="Select entity types"
      value={value}
      onChange={handleChange}
      disabled={disabled}
      style={{ width: '100%' }}
      options={entities.map((entity) => ({
        label: entity,
        value: entity,
      }))}
      tagRender={tagRender}
      showSearch
      filterOption={caseInsensitiveFilter}
      allowClear
    />
  );
}
