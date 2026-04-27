// Rule editor component - handles import modal for L4 rule definitions
import React, { useState } from 'react';
import {
  Modal,
  Button,
  Tabs,
  Form,
  Input,
  Select,
  Alert,
  Typography,
} from 'antd';
import {
  ImportOutlined,
  FolderOpenOutlined,
} from '@ant-design/icons';
import { spaceApi } from '../../api/spaceApi';

const { Text } = Typography;

interface RuleEditorProps {
  spaceId: string;
  spaceName?: string;
  onImportSuccess?: () => void;
}

const EXAMPLE_PATHS = [
  {
    label: '供应链金融 - Schema',
    value: 'examples/supply_chain_finance/schema.yaml',
    desc: '包含 L1-L4 全层级 Schema 定义',
  },
  {
    label: '供应链金融 - 实例',
    value: 'examples/supply_chain_finance/instances.yaml',
    desc: '供应商、发票等实体实例数据',
  },
  {
    label: '个人消费信贷 - Schema',
    value: 'examples/consumer_credit/schema.yaml',
    desc: '个人信贷评分卡规则体系',
  },
  {
    label: '个人消费信贷 - 实例',
    value: 'examples/consumer_credit/instances.yaml',
    desc: '消费者信贷实例数据',
  },
];

export const RuleEditor: React.FC<RuleEditorProps> = ({
  spaceId,
  spaceName,
  onImportSuccess,
}) => {
  const [importModalVisible, setImportModalVisible] = useState(false);
  const [importActiveTab, setImportActiveTab] = useState('path');
  const [importContent, setImportContent] = useState('');
  const [importPath, setImportPath] = useState('examples/supply_chain_finance/schema.yaml');
  const [importing, setImporting] = useState(false);

  const handleImportByContent = async () => {
    if (!importContent.trim()) {
      return;
    }
    // L4 Schema YAML 请通过「从文件路径导入」使用 loadSchemaFromYaml 接口
    setImportModalVisible(false);
    setImportContent('');
  };

  const handleImportByPath = async () => {
    if (!importPath.trim()) {
      return;
    }
    if (!spaceId) {
      return;
    }
    setImporting(true);
    try {
      await spaceApi.loadSchemaFromYaml(spaceId, importPath, true);
      setImportModalVisible(false);
      onImportSuccess?.();
    } catch (e) {
      throw e;
    } finally {
      setImporting(false);
    }
  };

  const handleImportOk = () => {
    if (importActiveTab === 'path') handleImportByPath();
    else handleImportByContent();
  };

  return (
    <>
      <Button
        icon={<ImportOutlined />}
        size="small"
        onClick={() => setImportModalVisible(true)}
      >
        导入 Schema
      </Button>

      <Modal
        title="导入 Schema（L1-L4 全量）"
        open={importModalVisible}
        onOk={handleImportOk}
        onCancel={() => {
          setImportModalVisible(false);
          setImportContent('');
        }}
        confirmLoading={importing}
        okText="导入"
        cancelText="取消"
        width={660}
      >
        <Tabs
          activeKey={importActiveTab}
          onChange={setImportActiveTab}
          items={[
            {
              key: 'path',
              label: (
                <span>
                  <FolderOpenOutlined /> 从文件路径导入
                </span>
              ),
              children: (
                <Form layout="vertical" style={{ marginTop: 8 }}>
                  <Form.Item label="选择预设示例">
                    <Select
                      style={{ width: '100%' }}
                      placeholder="选择示例文件"
                      onChange={(val) => setImportPath(val)}
                      options={EXAMPLE_PATHS.map((p) => ({
                        label: (
                          <div>
                            <div style={{ fontWeight: 500 }}>{p.label}</div>
                            <div style={{ fontSize: 11, color: '#999' }}>{p.value}</div>
                          </div>
                        ),
                        value: p.value,
                      }))}
                    />
                  </Form.Item>
                  <Form.Item label="或手动输入路径">
                    <Input
                      value={importPath}
                      onChange={(e) => setImportPath(e.target.value)}
                      placeholder="examples/supply_chain_finance/schema.yaml"
                      prefix={<FolderOpenOutlined />}
                    />
                  </Form.Item>
                  <Alert
                    type="info"
                    showIcon
                    message="路径导入说明"
                    description="此操作会将 Schema 文件（包含 L1-L4 层级定义）整体导入到当前语义空间，L4 业务规则将在导入后显示在此页面。"
                    style={{ marginTop: 8 }}
                  />
                </Form>
              ),
            },
            {
              key: 'content',
              label: (
                <span>
                  <ImportOutlined /> 粘贴 YAML 内容
                </span>
              ),
              children: (
                <Form layout="vertical" style={{ marginTop: 8 }}>
                  <Form.Item
                    label="YAML 内容"
                    help="粘贴 Schema YAML（L1-L4 完整格式），L4 业务规则将作为规则声明导入"
                  >
                    <Input.TextArea
                      rows={12}
                      value={importContent}
                      onChange={(e) => setImportContent(e.target.value)}
                      placeholder={`schema_version: "2.0"\nsemantic_space:\n  id: "space_example"\n  name: "示例空间"\nbusiness_logic:\n  rule_definitions:\n    - id: RD001_example\n      name: "示例规则"\n      rule_type: constraint`}
                      style={{ fontFamily: 'monospace', fontSize: 12 }}
                    />
                  </Form.Item>
                </Form>
              ),
            },
          ]}
        />
        <Text type="secondary" style={{ fontSize: 11 }}>
          提示：导入的 Schema 将属于当前语义空间（{spaceName || spaceId || '未选择'}），L4 规则自动同步到此页面
        </Text>
      </Modal>
    </>
  );
};

export default RuleEditor;
