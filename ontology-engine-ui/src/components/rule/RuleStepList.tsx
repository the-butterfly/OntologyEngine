// ontology-engine-ui/src/components/rule/RuleStepList.tsx
// Rule step list with drag-and-drop reordering support using @dnd-kit

import React, { useState, useEffect } from 'react';
import { Card, Button, Space, Tag, List, Popconfirm, message } from 'antd';
import {
  PlusOutlined,
  EditOutlined,
  DeleteOutlined,
  HolderOutlined,
} from '@ant-design/icons';
import { ruleGroupsApi } from '../../api/ruleGroups';
import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  DragEndEvent,
} from '@dnd-kit/core';
import {
  arrayMove,
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable';
import { CSS } from '@dnd-kit/utilities';
import type { RuleStep } from '../../types/rule';
import RuleEditorModal from './RuleEditorModal';

interface RuleStepListProps {
  schemaId: string;
  ruleGroupName: string;
  steps: RuleStep[];
  inputs?: Array<{ name: string; type?: string }>;
  outputs?: Array<{ name: string; type?: string }>;
  onStepsChange?: (steps: RuleStep[]) => void;
  onEditStep?: (step: RuleStep) => void;
  onDeleteStep?: (stepId: string) => void;
  onReorder?: (stepIds: string[]) => Promise<void>;
  disabled?: boolean;
  /** 当从外部传入一个 step 时，自动打开编辑 Modal（用于 deep link 编辑） */
  initialEditStep?: RuleStep | null;
  /** Called with step ID on hover enter, undefined on hover leave */
  onHoverStep?: (stepId: string | undefined) => void;
}

interface SortableItemProps {
  id: string;
  step: RuleStep;
  onEdit: () => void;
  onDelete: () => void;
  disabled: boolean;
  onHover?: (stepId: string | undefined) => void;
}

function SortableItem({ id, step, onEdit, onDelete, disabled, onHover }: SortableItemProps) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id, disabled });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  const getConditionText = (when: RuleStep['when']) => {
    if (when.type === 'expression') {
      return when.expression.substring(0, 50) + (when.expression.length > 50 ? '...' : '');
    }
    return `${when.type.toUpperCase()}: ${when.subConditions?.length || 0} conditions`;
  };

  return (
    <div ref={setNodeRef} style={style}>
      <List.Item
        onMouseEnter={() => onHover?.(step.id)}
        onMouseLeave={() => onHover?.(undefined)}
        actions={[
          <Button
            key="edit"
            type="text"
            icon={<EditOutlined />}
            onClick={onEdit}
            disabled={disabled}
          />,
          <Popconfirm
            key="delete"
            title="确定删除该规则?"
            onConfirm={onDelete}
            disabled={disabled}
          >
            <Button type="text" danger icon={<DeleteOutlined />} disabled={disabled} />
          </Popconfirm>,
        ]}
        style={{
          background: '#fff',
          borderRadius: 4,
          padding: '8px 12px',
          marginBottom: 8,
          border: '1px solid #f0f0f0',
        }}
      >
        <List.Item.Meta
          avatar={
            <Button
              type="text"
              icon={<HolderOutlined />}
              {...attributes}
              {...listeners}
              style={{ cursor: 'grab' }}
              disabled={disabled}
            />
          }
          title={
            <Space>
              <span>{step.name}</span>
              {!step.enabled && <Tag color="default">禁用</Tag>}
              <Tag color={step.when.type === 'expression' ? 'blue' : 'cyan'}>
                {step.when.type.toUpperCase()}
              </Tag>
            </Space>
          }
          description={
            <Space direction="vertical" size="small" style={{ width: '100%' }}>
              <div style={{ fontSize: 12, color: '#666' }}>
                <span style={{ fontWeight: 500 }}>条件: </span>
                {getConditionText(step.when)}
              </div>
              <div style={{ fontSize: 12, color: '#666' }}>
                <span style={{ fontWeight: 500 }}>动作: </span>
                {step.then.operator}
              </div>
            </Space>
          }
        />
      </List.Item>
    </div>
  );
}

export default function RuleStepList({
  schemaId,
  ruleGroupName,
  steps,
  inputs = [],
  outputs = [],
  onStepsChange,
  onEditStep,
  onDeleteStep,
  onReorder,
  disabled = false,
  initialEditStep,
  onHoverStep,
}: RuleStepListProps) {
  const [modalOpen, setModalOpen] = useState(false);
  const [editingStep, setEditingStep] = useState<Partial<RuleStep> | undefined>();
  const [localSteps, setLocalSteps] = useState<RuleStep[]>(steps);
  const [reordering, setReordering] = useState(false);
  const [saving, setSaving] = useState(false);

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  // Sync with props
  useEffect(() => {
    setLocalSteps(steps);
  }, [steps]);

  // Respond to initialEditStep prop (from deep link editStepId)
  useEffect(() => {
    if (initialEditStep) {
      setEditingStep(initialEditStep);
      setModalOpen(true);
    }
  }, [initialEditStep]);

  const handleDragEnd = async (event: DragEndEvent) => {
    const { active, over } = event;

    if (over && active.id !== over.id) {
      const oldIndex = localSteps.findIndex((s) => s.id === active.id);
      const newIndex = localSteps.findIndex((s) => s.id === over.id);
      const newSteps = arrayMove(localSteps, oldIndex, newIndex);

      setLocalSteps(newSteps);
      onStepsChange?.(newSteps);

      // Call reorder API
      if (onReorder) {
        setReordering(true);
        try {
          const stepIds = newSteps.map((s) => s.id);
          await onReorder(stepIds);
          message.success('排序已保存');
        } catch {
          message.error('排序保存失败');
          // Revert on failure
          setLocalSteps(steps);
        } finally {
          setReordering(false);
        }
      }
    }
  };

  const handleAdd = () => {
    setEditingStep({
      name: '',
      enabled: true,
      when: { type: 'expression', expression: '' },
      then: { operator: 'COMPUTE', params: {}, outputMapping: {} },
      tags: [],
    });
    setModalOpen(true);
  };

  const handleEdit = (step: RuleStep) => {
    setEditingStep(step);
    setModalOpen(true);
    onEditStep?.(step);
  };

  const handleDelete = (stepId: string) => {
    onDeleteStep?.(stepId);
  };

  const handleSave = async (updatedStep: Partial<RuleStep>) => {
    if (!ruleGroupName || !schemaId) return;
    setSaving(true);
    try {
      let updatedSteps: RuleStep[];
      if (updatedStep.id) {
        // 编辑已有步骤
        const result = await ruleGroupsApi.updateStep(ruleGroupName, updatedStep.id, updatedStep, schemaId);
        updatedSteps = localSteps.map(s => s.id === updatedStep.id ? result : s);
        message.success('步骤已更新');
      } else {
        // 新增步骤
        const result = await ruleGroupsApi.addStep(ruleGroupName, updatedStep, schemaId);
        updatedSteps = [...localSteps, result];
        message.success('步骤已添加');
      }
      setLocalSteps(updatedSteps);
      setModalOpen(false);
      setEditingStep(undefined);
      onStepsChange?.(updatedSteps);
    } catch (err) {
      message.error(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    setModalOpen(false);
    setEditingStep(undefined);
  };

  return (
    <Card
      size="small"
      title="规则实例"
      extra={
        <Button
          type="primary"
          size="small"
          icon={<PlusOutlined />}
          onClick={handleAdd}
          disabled={disabled}
        >
          添加规则
        </Button>
      }
    >
      {localSteps.length === 0 ? (
        <div style={{ textAlign: 'center', padding: '20px', color: '#999' }}>
          暂无规则实例，点击"添加规则"创建
        </div>
      ) : (
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragEnd={handleDragEnd}
        >
          <SortableContext
            items={localSteps.map((s) => s.id)}
            strategy={verticalListSortingStrategy}
          >
            {localSteps.map((step) => (
              <SortableItem
                key={step.id}
                id={step.id}
                step={step}
                onEdit={() => handleEdit(step)}
                onDelete={() => handleDelete(step.id)}
                disabled={disabled || reordering}
                onHover={onHoverStep}
              />
            ))}
          </SortableContext>
        </DndContext>
      )}

      <RuleEditorModal
        open={modalOpen}
        ruleGroupName={ruleGroupName}
        schemaId={schemaId}
        step={editingStep}
        inputs={inputs}
        outputs={outputs}
        onSave={handleSave}
        onCancel={handleCancel}
        saving={saving}
      />
    </Card>
  );
}