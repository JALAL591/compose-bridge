package com.composebridge.agent

/**
 * Prints structured JSON to Logcat
 * 
 * Splits JSON into chunks because Logcat truncates long lines
 * Each chunk has a consistent prefix for easy reassembly.
 */
object BridgeDebugPrinter {

    private const val CHUNK_SIZE = 800
    private const val TAG_PREFIX = "[ComposeBridge-JSON]"

    fun printJson(json: String, label: String = "SNAPSHOT") {
        println("$TAG_PREFIX ===START:$label===")
        
        // Split JSON into chunks
        var i = 0
        while (i < json.length) {
            val end = minOf(i + CHUNK_SIZE, json.length)
            val chunk = json.substring(i, end)
            println("$TAG_PREFIX $chunk")
            i = end
        }
        
        println("$TAG_PREFIX ===END:$label===")
    }

    /**
     * Print readable tree with clear markers
     * For visual inspection only
     */
    fun printHumanReadable(node: BridgeNode, depth: Int = 0, treeIdx: Int = 0) {
        if (!node.isUserNode()) {
            // Do not print, but inspect children
            node.children.forEach { printHumanReadable(it, depth, treeIdx) }
            return
        }
        
        val indent = "  ".repeat(depth)
        val src = "${node.sourceFile}:${node.line}"
        val offset = "off=${node.utf16Offset}"
        val length = "len=${node.utf16Length}"
        val bounds = "(${node.left},${node.top})-(${node.right},${node.bottom})"
        
        println("[ComposeBridge] $indent[tree$treeIdx] ${node.name ?: "?"} @ $src | $offset | $length | $bounds")
        
        node.children.forEach { printHumanReadable(it, depth + 1, treeIdx) }
    }

    /**
     * Print clean filtered tree without noise
     */
    fun printFilteredTree(node: BridgeNode?, depth: Int = 0, treeIdx: Int = 0) {
        if (node == null) {
            println("[ComposeBridge] tree$treeIdx = (empty)")
            return
        }
        val indent = "  ".repeat(depth)
        val src = "${node.sourceFile}:${node.line}"
        val meta = "off=${node.utf16Offset} len=${node.utf16Length}"
        val bounds = "(${node.left},${node.top})-(${node.right},${node.bottom})"
        println("[ComposeBridge] $indent[tree$treeIdx] ${node.name ?: "?"} @ $src | $meta | $bounds")
        node.children.forEach { printFilteredTree(it, depth + 1, treeIdx) }
    }
}
