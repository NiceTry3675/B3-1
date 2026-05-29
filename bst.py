"""Binary search tree implementation for the bonus assignment."""

from dynamic_array import DynamicArray


class BSTNode:
    def __init__(self, key, value=None):
        self.key = key
        self.value = value
        self.left = None
        self.right = None


class BinarySearchTree:
    """BST with insert, search, delete, and sorted inorder traversal."""

    def __init__(self):
        self.root = None
        self._size = 0

    def size(self):
        return self._size

    def insert(self, key, value=None):
        if self.root is None:
            self.root = BSTNode(key, value)
            self._size += 1
            return True
        node = self.root
        while True:
            if key == node.key:
                node.value = value
                return False
            if key < node.key:
                if node.left is None:
                    node.left = BSTNode(key, value)
                    self._size += 1
                    return True
                node = node.left
            else:
                if node.right is None:
                    node.right = BSTNode(key, value)
                    self._size += 1
                    return True
                node = node.right

    def search(self, key):
        node = self.root
        while node is not None:
            if key == node.key:
                return node.value
            if key < node.key:
                node = node.left
            else:
                node = node.right
        return None

    def delete(self, key):
        deleted, self.root = self._delete(self.root, key)
        if deleted:
            self._size -= 1
        return deleted

    def inorder_keys(self):
        result = DynamicArray()
        self._inorder(self.root, result)
        return result

    def _delete(self, node, key):
        if node is None:
            return False, None
        if key < node.key:
            deleted, node.left = self._delete(node.left, key)
            return deleted, node
        if key > node.key:
            deleted, node.right = self._delete(node.right, key)
            return deleted, node
        if node.left is None:
            return True, node.right
        if node.right is None:
            return True, node.left
        successor = self._min_node(node.right)
        node.key = successor.key
        node.value = successor.value
        _, node.right = self._delete(node.right, successor.key)
        return True, node

    def _min_node(self, node):
        while node.left is not None:
            node = node.left
        return node

    def _inorder(self, node, result):
        if node is None:
            return
        self._inorder(node.left, result)
        result.append(node.key)
        self._inorder(node.right, result)
