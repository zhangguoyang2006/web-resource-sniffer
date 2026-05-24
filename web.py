import streamlit as st
import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import heapq
from datetime import datetime

class WebResourceSniffer:
    def __init__(self, start_url):
        self.start_url = start_url
        
        # 核心改动 1：根据当前时间生成唯一的文件夹，实现物理资源的隔离
        session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.download_dir = os.path.join('downloads', session_id)
        
        self.hash_table_dedup = set() 
        self.priority_queue = [] 
        
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def fetch_html(self, url):
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            return response.text
        except requests.exceptions.RequestException as e:
            st.error(f"网络请求失败或网址无效: {e}")
            return None

    def traverse_dom_tree_dfs(self, html_content, base_url):
        soup = BeautifulSoup(html_content, 'html.parser')
        stack = [soup] 

        while stack:
            current_node = stack.pop()
            
            if current_node.name is not None:
                resource_url = None
                priority = 99
                res_type = "unknown"

                if current_node.name == 'link' and 'stylesheet' in current_node.get('rel', []):
                    resource_url = current_node.get('href')
                    priority, res_type = 1, 'CSS'
                elif current_node.name == 'script' and current_node.has_attr('src'):
                    resource_url = current_node.get('src')
                    priority, res_type = 2, 'JS'
                elif current_node.name == 'img' and current_node.has_attr('src'):
                    resource_url = current_node.get('src')
                    priority, res_type = 3, 'Image' 
                elif current_node.name == 'video' and current_node.has_attr('src'):
                    resource_url = current_node.get('src')
                    priority, res_type = 4, 'Video'
                elif current_node.name == 'source' and 'video' in current_node.get('type', ''):
                    resource_url = current_node.get('src')
                    priority, res_type = 4, 'Video'

                if resource_url:
                    full_url = urllib.parse.urljoin(base_url, resource_url)
                    if full_url not in self.hash_table_dedup and not full_url.startswith('data:'):
                        self.hash_table_dedup.add(full_url)
                        heapq.heappush(self.priority_queue, (priority, res_type, full_url))

            if hasattr(current_node, 'children'):
                for child in current_node.children:
                    if child.name is not None:
                        stack.append(child)

    def download_image(self, resource_url):
        try:
            filename = os.path.basename(urllib.parse.urlparse(resource_url).path)
            if not filename: return None
            if filename.endswith('.svg'): return None 
                
            filepath = os.path.join(self.download_dir, filename)
            if not os.path.exists(filepath):
                response = requests.get(resource_url, stream=True, timeout=5)
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            return filepath
        except Exception:
            return None

    def execute_scheduler(self):
        results = {'CSS': [], 'JS': [], 'Video': [], 'Image_Paths': []}
        while self.priority_queue:
            priority, res_type, url = heapq.heappop(self.priority_queue)
            
            if res_type in ['CSS', 'JS', 'Video']:
                results[res_type].append(url)
            elif res_type == 'Image':
                filepath = self.download_image(url)
                if filepath:
                    results['Image_Paths'].append(filepath)
        return results

# ==========================================
# 前端界面构建
# ==========================================
st.set_page_config(page_title="资源嗅探器", layout="wide")

# 核心改动 2：初始化系统的“记忆” (会话状态)
if 'sniff_history' not in st.session_state:
    st.session_state.sniff_history = []

st.title("🌐 基于树遍历算法的轻量级网页资源嗅探与调度工具")
st.markdown("集成 **DFSDOM树解析** | **哈希表极速去重** | **优先队列自动调度**")
st.markdown("---")

# 顶部交互区
col_input, col_btn = st.columns([4, 1])
with col_input:
    target_url = st.text_input("🔗 请输入要嗅探的目标网址 (URL)：", "https://www.apple.com.cn/")
with col_btn:
    st.write("") # 占位对齐
    st.write("")
    start_btn = st.button("🚀 开始嗅探并调度", use_container_width=True)

if start_btn:
    if not target_url:
        st.warning("网址不能为空！")
    else:
        with st.spinner("正在构建 DOM 树并执行深度优先遍历..."):
            sniffer = WebResourceSniffer(target_url)
            html = sniffer.fetch_html(target_url)
            
            if html:
                sniffer.traverse_dom_tree_dfs(html, target_url)
                results = sniffer.execute_scheduler()
                
                # 将本次结果打包存入历史记录，插在列表最前面（最新的在最上）
                record = {
                    'time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    'url': target_url,
                    'data': results
                }
                st.session_state.sniff_history.insert(0, record)
                st.toast("🎉 调度任务全部完成并已存入历史记录！")

# ==========================================
# 历史记录展示区 (折叠面板)
# ==========================================
st.markdown("### 📂 嗅探历史档案馆")

if not st.session_state.sniff_history:
    st.info("暂无嗅探记录。在上方输入网址开始第一次嗅探吧！")
else:
    # 遍历展示每一次的历史记录
    for idx, record in enumerate(st.session_state.sniff_history):
        # 默认只展开最新的一次嗅探结果 (idx == 0)
        with st.expander(f"🕒 {record['time']} | 🔗 目标: {record['url']}", expanded=(idx == 0)):
            res_data = record['data']
            col1, col2 = st.columns(2)
            
            with col1:
                st.write(f"**🎨 CSS 样式表 ({len(res_data['CSS'])}):**")
                with st.container(height=150): # 限制高度并添加滚动条
                    for css in res_data['CSS']: st.code(css, language='text')
                    
                st.write(f"**⚙️ JS 脚本 ({len(res_data['JS'])}):**")
                with st.container(height=150):
                    for js in res_data['JS']: st.code(js, language='text')
                    
                st.write(f"**▶️ 受保护视频源 ({len(res_data['Video'])}):**")
                if res_data['Video']:
                    for vid in res_data['Video']: st.code(vid, language='text')
                else:
                    st.caption("未嗅探到视频。")
            
            with col2:
                st.write(f"**🖼️ 下载的图片 ({len(res_data['Image_Paths'])})**")
                if res_data['Image_Paths']:
                    img_cols = st.columns(3)
                    for i, img_path in enumerate(res_data['Image_Paths']):
                        with img_cols[i % 3]:
                            st.image(img_path, use_container_width=True)
                else:
                    st.caption("未成功下载符合规则的图片。")