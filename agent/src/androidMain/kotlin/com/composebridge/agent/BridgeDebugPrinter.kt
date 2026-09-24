package com.composebridge.agent

/**
 * Formatted JSON printing for Logcat
 * 
 * Logcat JSON chunks
 * Each chunk has a fixed prefix for easy reassembly.
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
 * Print readable tree structure with clear markers 
 * For visual inspection use only
 */
 fun printHumanReadable(node: BridgeNode, depth: Int = 0, treeIdx: Int = 0) {
 if (!node.isUserNode()) {
 // Do not print, search in children
 node.children.forEach { printHumanReadable(it, depth, treeIdx) }
 return
 }
 
 val indent = " ".repeat(depth)
 val src = "${node.sourceFile}:${node.line}"
 val offset = "off=${node.utf16Offset}"
 val length = "len=${node.utf16Length}"
 val bounds = "(${node.left},${node.top})-(${node.right},${node.bottom})"
 
 println("[ComposeBridge] $indent[tree$treeIdx] ${node.name ?: "?"} @ $src | $offset | $length | $bounds")
 
 node.children.forEach { printHumanReadable(it, depth + 1, treeIdx) }
 }

 /**
 * ( )
 */
 fun printFilteredTree(node: BridgeNode?, depth: Int = 0, treeIdx: Int = 0) {
 if (node == null) {
 println("[ComposeBridge] tree$treeIdx = (empty)")
 return
 }
 val indent = " ".repeat(depth)
 val src = "${node.sourceFile}:${node.line}"
 val meta = "off=${node.utf16Offset} len=${node.utf16Length}"
 val bounds = "(${node.left},${node.top})-(${node.right},${node.bottom})"
 println("[ComposeBridge] $indent[tree$treeIdx] ${node.name ?: "?"} @ $src | $meta | $bounds")
 node.children.forEach { printFilteredTree(it, depth + 1, treeIdx) }
 }
}