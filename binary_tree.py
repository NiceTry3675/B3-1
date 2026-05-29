"""Binary tree and traversal algorithms for the bonus assignment."""

from dynamic_array import DynamicArray
from linked_list import DoublyLinkedList


class BinaryTreeNode:
    def __init__(self, value):
        self.value = value
        self.left = None
        self.right = None


class BinaryTree:
    """General binary tree with preorder, inorder, postorder, and levelorder."""

    def __init__(self, root=None):
        self.root = root

    def preorder(self):
        result = DynamicArray()
        self._preorder(self.root, result)
        return result

    def inorder(self):
        result = DynamicArray()
        self._inorder(self.root, result)
        return result

    def postorder(self):
        result = DynamicArray()
        self._postorder(self.root, result)
        return result

    def levelorder(self):
        result = DynamicArray()
        if self.root is None:
            return result
        queue = DoublyLinkedList()
        queue.insert_back(self.root)
        while queue.size() > 0:
            node = queue.remove_front()
            result.append(node.value)
            if node.left is not None:
                queue.insert_back(node.left)
            if node.right is not None:
                queue.insert_back(node.right)
        return result

    def _preorder(self, node, result):
        if node is None:
            return
        result.append(node.value)
        self._preorder(node.left, result)
        self._preorder(node.right, result)

    def _inorder(self, node, result):
        if node is None:
            return
        self._inorder(node.left, result)
        result.append(node.value)
        self._inorder(node.right, result)

    def _postorder(self, node, result):
        if node is None:
            return
        self._postorder(node.left, result)
        self._postorder(node.right, result)
        result.append(node.value)
