import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
import heapq  # 引入优先队列 (基于堆)

class WebResourceSniffer:
    def __init__(self, start_url):
        self.start_url = start_url
        self.download_dir = 'downloads'
        
        # 1. 哈希表 (Hash Table)：用于极速去重，记录已发现的资源 URL
        self.hash_table_dedup = set() 
        
        # 2. 优先队列 (Priority Queue)：用于资源调度
        # 存入格式: (优先级数字, 资源类型, 资源URL) - 数字越小优先级越高
        self.priority_queue = [] 
        
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

    def fetch_html(self, url):
        """发送网络请求获取网页内容"""
        print(f"[*] 正在尝试连接目标网址: {url}")
        try:
            headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
            response = requests.get(url, headers=headers, timeout=5)
            response.raise_for_status()
            print("[+] 网页内容获取成功，准备构建 DOM 树...")
            return response.text
        except requests.exceptions.RequestException as e:
            print(f"[!] 网络请求失败: {e}")
            return None

    def traverse_dom_tree_dfs(self, html_content, base_url):
        """
        核心算法：基于【栈】的 DOM 树深度优先遍历 (DFS)
        利用字符串匹配和节点属性提取资源
        """
        soup = BeautifulSoup(html_content, 'html.parser')
        stack = [soup] # 使用栈辅助 DFS 遍历
        
        print("[*] 启动 DFS 深度优先遍历算法，开始嗅探资源...")

        while stack:
            current_node = stack.pop()
            
            # --- 资源提取与优先级设定 ---
            if current_node.name is not None:
                resource_url = None
                priority = 99
                res_type = "unknown"

                # 提取 CSS (优先级 1)
                if current_node.name == 'link' and 'stylesheet' in current_node.get('rel', []):
                    resource_url = current_node.get('href')
                    priority, res_type = 1, 'CSS'
                
                # 提取 JS (优先级 2)
                elif current_node.name == 'script' and current_node.has_attr('src'):
                    resource_url = current_node.get('src')
                    priority, res_type = 2, 'JS'
                
                # 提取 图片 (优先级 3)
                elif current_node.name == 'img' and current_node.has_attr('src'):
                    resource_url = current_node.get('src')
                    priority, res_type = 3, 'Image'
                
                # 提取 视频 (优先级 4)
                elif current_node.name == 'video' and current_node.has_attr('src'):
                    resource_url = current_node.get('src')
                    priority, res_type = 4, 'Video'
                elif current_node.name == 'source' and 'video' in current_node.get('type', ''):
                    resource_url = current_node.get('src')
                    priority, res_type = 4, 'Video'

                # --- 哈希表去重与入队 ---
                if resource_url:
                    full_url = urllib.parse.urljoin(base_url, resource_url)
                    # 利用哈希表 O(1) 复杂度去重
                    if full_url not in self.hash_table_dedup and not full_url.startswith('data:'):
                        self.hash_table_dedup.add(full_url)
                        # 压入优先队列进行调度
                        heapq.heappush(self.priority_queue, (priority, res_type, full_url))

            # 遍历子节点并压入栈
            if hasattr(current_node, 'children'):
                for child in current_node.children:
                    if child.name is not None:
                        stack.append(child)
                        
        print(f"[+] 遍历结束，哈希表共拦截并去重后保留 {len(self.priority_queue)} 个有效资源进入优先队列。")

    def download_image(self, resource_url):
        """轻量级下载函数，仅下载图片"""
        try:
            filename = os.path.basename(urllib.parse.urlparse(resource_url).path)
            if not filename: return False
            if filename.endswith('.svg'): return False # 过滤小图标
                
            filepath = os.path.join(self.download_dir, filename)
            if not os.path.exists(filepath):
                response = requests.get(resource_url, stream=True, timeout=5)
                with open(filepath, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        f.write(chunk)
            return True
        except Exception:
            return False

    def execute_scheduler(self):
        """调度器：根据优先级队列处理资源"""
        print("\n" + "="*40)
        print("🚀 启动资源调度器 (优先队列出队执行)")
        print("="*40)
        
        # 只要优先队列不为空，就按优先级弹出处理
        while self.priority_queue:
            # 弹出优先级最高的资源
            priority, res_type, url = heapq.heappop(self.priority_queue)
            
            # 打印调度日志
            if res_type in ['CSS', 'JS']:
                print(f"[优先调度] 核心代码 [{res_type}]: 成功提取链接 -> {url[:60]}...")
            elif res_type == 'Video':
                print(f"[提取源站] 视频链接 [{res_type}]: 成功提取源 -> {url[:60]}...")
            elif res_type == 'Image':
                success = self.download_image(url)
                if success:
                    print(f"[滞后调度] 媒体文件 [{res_type}]: 触发下载并存入本地 -> {url[:60]}...")
                    
        print("="*40)
        print("🎉 所有队列调度完毕，任务结束！")

# ==========================================
# 程序执行入口
# ==========================================
if __name__ == "__main__":
    # 可以替换为你想要测试的网址
    TARGET_URL = "https://en.wikipedia.org/wiki/Data_structure" 
    
    print("=== 初始化基于树遍历的轻量级资源嗅探与调度工具 ===")
    sniffer = WebResourceSniffer(TARGET_URL)
    
    html = sniffer.fetch_html(TARGET_URL)
    if html:
        sniffer.traverse_dom_tree_dfs(html, TARGET_URL)
        sniffer.execute_scheduler()