package com.composebridge.agent

import android.annotation.SuppressLint
import android.content.Context
import android.graphics.Canvas
import android.graphics.Color
import android.graphics.Paint
import android.graphics.Rect
import android.view.MotionEvent
import android.view.View
import kotlin.math.sqrt

/**
 * Transparent Overlay over the entire screen.
 *
 * - In normal mode: Does not intercept touch (passthrough).
 * - In design mode: Intercepts touch, selects element, draws border around it.
 */
@SuppressLint("ViewConstructor")
class BridgeSelectionOverlay(
    context: Context,
    private val getTrees: () -> List<BridgeNode>,
    private val onSelect: (BridgeHitTester.HitResult?) -> Unit
) : View(context) {

    var isActive: Boolean = false
        set(value) {
            field = value
            invalidate()
        }

    var onStopRequested: (() -> Unit)? = null

    private var highlightRect: Rect? = null
    private var selectedLabel: String? = null
    private var currentNode: BridgeNode? = null

    // ⭐ Preview during drag
    private var previewRect: Rect? = null
    private var draggingHandle: HandleType? = null
    private var dragStartX = 0f
    private var dragStartY = 0f
    private var originalBounds: Rect? = null

    enum class HandleType { TOP_LEFT, TOP_RIGHT, BOTTOM_LEFT, BOTTOM_RIGHT }

    private val handleRadius = 35f

    private val handlePaint = Paint().apply {
        color = Color.rgb(0, 200, 150)
        style = Paint.Style.FILL
        isAntiAlias = true
    }
    private val handleBorderPaint = Paint().apply {
        color = Color.WHITE
        style = Paint.Style.STROKE
        strokeWidth = 4f
        isAntiAlias = true
    }

    private val borderPaint = Paint().apply {
        color = Color.rgb(0, 200, 150)
        style = Paint.Style.STROKE
        strokeWidth = 4f
        isAntiAlias = true
    }

    private val fillPaint = Paint().apply {
        color = Color.argb(60, 0, 200, 150)
        style = Paint.Style.FILL
    }

    // ⭐ Semi-transparent light green preview
    private val previewFillPaint = Paint().apply {
        color = Color.argb(80, 0, 230, 180)
        style = Paint.Style.FILL
    }
    private val previewBorderPaint = Paint().apply {
        color = Color.rgb(0, 230, 180)
        style = Paint.Style.STROKE
        strokeWidth = 6f
        isAntiAlias = true
    }

    private val labelPaint = Paint().apply {
        color = Color.WHITE
        textSize = 32f
        isAntiAlias = true
    }

    private val labelBgPaint = Paint().apply {
        color = Color.rgb(76, 76, 217)
        style = Paint.Style.FILL
    }

    // Close button target aligned with DesignModeButton (statusBarsPadding + 80dp top, 16dp end)
    private fun getStopButtonRect(): Rect {
        val density = resources.displayMetrics.density
        val statusBarHeight = run {
            val resId = resources.getIdentifier("status_bar_height", "dimen", "android")
            if (resId > 0) resources.getDimensionPixelSize(resId) else (24 * density).toInt()
        }
        val topOffset = statusBarHeight + (80 * density).toInt()
        val size = (56 * density).toInt()
        val margin = (16 * density).toInt()
        val isRtl = resources.configuration.layoutDirection == View.LAYOUT_DIRECTION_RTL
        val left = if (isRtl) margin else width - margin - size
        val right = left + size
        val bottom = topOffset + size
        val slop = (8 * density).toInt()
        return Rect(left - slop, topOffset - slop, right + slop, bottom + slop)
    }

    private var overlayLocation = IntArray(2)

    init {
        setBackgroundColor(Color.TRANSPARENT)
        isClickable = false
        isFocusable = false
    }

    override fun onTouchEvent(event: MotionEvent): Boolean {
        if (!isActive) return false

        val localX = event.x
        val localY = event.y

        when (event.actionMasked) {
            MotionEvent.ACTION_DOWN -> {
                // Close button
                if (getStopButtonRect().contains(localX.toInt(), localY.toInt())) {
                    return true
                }

                // Is touch on a handle?
                val handle = findHandle(localX, localY)
                if (handle != null) {
                    draggingHandle = handle
                    dragStartX = localX
                    dragStartY = localY
                    originalBounds = highlightRect?.let { Rect(it) }
                    return true
                }
                return true
            }

            MotionEvent.ACTION_MOVE -> {
                if (draggingHandle != null && originalBounds != null) {
                    val dx = localX - dragStartX
                    val dy = localY - dragStartY
                    updatePreview(dx, dy)
                    invalidate()
                    return true
                }
                return true
            }

            MotionEvent.ACTION_UP -> {
                // Close button
                if (getStopButtonRect().contains(localX.toInt(), localY.toInt())) {
                    onStopRequested?.invoke()
                    draggingHandle = null
                    previewRect = null
                    invalidate()
                    return true
                }

                // Finish drag
                if (draggingHandle != null) {
                    // ⭐ Preview only — no file writes
                    previewRect?.let { highlightRect = Rect(it) }
                    draggingHandle = null
                    originalBounds = null
                    previewRect = null
                    invalidate()
                    println("[Overlay] 👁️ Preview only — use Slider to edit source")
                    return true
                }

                // Select new element
                val result = BridgeHitTester.hitTest(getTrees(), localX.toInt(), localY.toInt())
                highlightRect = result?.node?.let {
                    Rect(it.left, it.top, it.right, it.bottom)
                }
                currentNode = result?.node
                selectedLabel = result?.node?.let {
                    "${it.name ?: "?"} @ ${it.sourceFile}:${it.line}"
                }
                invalidate()

                println(BridgeHitTester.formatResult(result))
                onSelect(result)

                result?.node?.let { node ->
                    // ⭐ 1. Clear old data immediately
                    BridgeState.elementColors.clear()
                    BridgeState.elementDimensions.clear()
                    BridgeState.elementComposableName = ""
                    BridgeState.isLoadingElementColors = true
                    BridgeState.elementAnalysisError = null

                    // ⭐ 2. New request with ID
                    val requestId = System.currentTimeMillis()
                    BridgeState.currentRequestId = requestId

                    DesignModeRegistry.selectedSourceFile = node.sourceFile
                    DesignModeRegistry.selectedSourceLine = node.line ?: 0
                    DesignModeRegistry.selectedElement = node.name

                    val file = node.sourceFile
                    val line = node.line
                    val offset = node.utf16Offset ?: 0
                    val length = node.utf16Length ?: 0
                    if (file != null && line != null && line > 0) {
                        // ⭐ Build tree JSON
                        val treeJson = buildChildrenJson(node)
                        val sent = ComposeBridgeAgent.analyzeElementWithTree(
                            file = file,
                            line = line,
                            utf16Offset = offset,
                            utf16Length = length,
                            treeJson = treeJson,
                            requestId = requestId,
                        )
                        println("[Overlay] 📤 analyzeElementWithTree sent=$sent (reqId=$requestId)")
                    }
                }
                return true
            }
        }
        return true
    }

    /**
     * Builds tree JSON — skips internal elements (_group, remember).
     */
    private fun buildChildrenJson(node: BridgeNode): String {
        return try {
            val realChildren = collectRealChildren(node, 0, 3)
            buildString {
                append("[")
                realChildren.forEachIndexed { index, child ->
                    if (index > 0) append(",")
                    append(child)
                }
                append("]")
            }
        } catch (e: Exception) {
            "[]"
        }
    }

    /**
     * Collects real elements (with sourceFile) recursively.
     * Skips _group and remember.
     */
    private fun collectRealChildren(node: BridgeNode, depth: Int, maxDepth: Int): List<String> {
        if (depth > maxDepth) return emptyList()
        
        val result = mutableListOf<String>()
        
        node.children.forEach { child ->
            val name = child.name ?: ""
            val file = child.sourceFile
            
            // Skip internal elements
            val isInternal = name == "_group" ||
                             name == "remember" ||
                             file == null ||
                             file.isEmpty() ||
                             file.contains("ComposableLambda") ||
                             file.contains("VectorPainter") ||
                             file.contains("Scaffold.kt")
            
            if (isInternal) {
                // Search inside _group for real children
                result.addAll(collectRealChildren(child, depth, maxDepth))
            } else {
                // Real element — add node and its children
                val childJson = buildRealNodeJson(child, depth)
                result.add(childJson)
            }
        }
        
        return result
    }

    /**
     * Builds JSON for real element with its real children.
     */
    private fun buildRealNodeJson(node: BridgeNode, depth: Int): String {
        val name = node.name ?: "_"
        val file = node.sourceFile ?: ""
        val line = node.line ?: 0
        val offset = node.utf16Offset ?: 0
        val length = node.utf16Length ?: 0
        
        // Collect real children
        val realChildren = collectRealChildren(node, depth + 1, depth + 3)
        val childrenJson = buildString {
            append("[")
            realChildren.forEachIndexed { index, child ->
                if (index > 0) append(",")
                append(child)
            }
            append("]")
        }
        
        return """{"name":"$name","sourceFile":"$file","line":$line,"utf16Offset":$offset,"utf16Length":$length,"children":$childrenJson}"""
    }

    private fun findHandle(x: Float, y: Float): HandleType? {
        val rect = highlightRect ?: return null
        getLocationOnScreen(overlayLocation)
        val ox = overlayLocation[0].toFloat()
        val oy = overlayLocation[1].toFloat()

        val left = rect.left - ox
        val top = rect.top - oy
        val right = rect.right - ox
        val bottom = rect.bottom - oy

        val threshold = handleRadius * 1.8f
        if (distance(x, y, left, top) < threshold) return HandleType.TOP_LEFT
        if (distance(x, y, right, top) < threshold) return HandleType.TOP_RIGHT
        if (distance(x, y, left, bottom) < threshold) return HandleType.BOTTOM_LEFT
        if (distance(x, y, right, bottom) < threshold) return HandleType.BOTTOM_RIGHT
        return null
    }

    private fun distance(x1: Float, y1: Float, x2: Float, y2: Float): Float {
        val dx = x1 - x2
        val dy = y1 - y2
        return sqrt(dx * dx + dy * dy)
    }

    /**
     * ⭐ Updates previewRect based on drag.
     */
    private fun updatePreview(dx: Float, dy: Float) {
        val orig = originalBounds ?: return
        val handle = draggingHandle ?: return

        val newRect = Rect(orig)

        when (handle) {
            HandleType.TOP_LEFT -> {
                newRect.left = (orig.left + dx).toInt()
                newRect.top = (orig.top + dy).toInt()
            }
            HandleType.TOP_RIGHT -> {
                newRect.right = (orig.right + dx).toInt()
                newRect.top = (orig.top + dy).toInt()
            }
            HandleType.BOTTOM_LEFT -> {
                newRect.left = (orig.left + dx).toInt()
                newRect.bottom = (orig.bottom + dy).toInt()
            }
            HandleType.BOTTOM_RIGHT -> {
                newRect.right = (orig.right + dx).toInt()
                newRect.bottom = (orig.bottom + dy).toInt()
            }
        }

        // ⚠️ Ensure dimensions are positive
        if (newRect.width() < 20 || newRect.height() < 20) return

        previewRect = newRect
    }

    override fun onDraw(canvas: Canvas) {
        super.onDraw(canvas)

        if (!isActive) return

        getLocationOnScreen(overlayLocation)
        val offsetX = overlayLocation[0].toFloat()
        val offsetY = overlayLocation[1].toFloat()

        // ⭐ Drag preview (if active)
        previewRect?.let { preview ->
            val drawPreview = Rect(
                (preview.left - offsetX).toInt(),
                (preview.top - offsetY).toInt(),
                (preview.right - offsetX).toInt(),
                (preview.bottom - offsetY).toInt(),
            )
            canvas.drawRect(drawPreview, previewFillPaint)
            canvas.drawRect(drawPreview, previewBorderPaint)
        }

        // Main border
        highlightRect?.let { rect ->
            val drawRect = Rect(
                (rect.left - offsetX).toInt(),
                (rect.top - offsetY).toInt(),
                (rect.right - offsetX).toInt(),
                (rect.bottom - offsetY).toInt(),
            )

            canvas.drawRect(drawRect, fillPaint)
            canvas.drawRect(drawRect, borderPaint)

            // ⭐ Draw 4 corner handles
            val r = handleRadius
            canvas.drawCircle(drawRect.left.toFloat(), drawRect.top.toFloat(), r, handlePaint)
            canvas.drawCircle(drawRect.left.toFloat(), drawRect.top.toFloat(), r, handleBorderPaint)
            canvas.drawCircle(drawRect.right.toFloat(), drawRect.top.toFloat(), r, handlePaint)
            canvas.drawCircle(drawRect.right.toFloat(), drawRect.top.toFloat(), r, handleBorderPaint)
            canvas.drawCircle(drawRect.left.toFloat(), drawRect.bottom.toFloat(), r, handlePaint)
            canvas.drawCircle(drawRect.left.toFloat(), drawRect.bottom.toFloat(), r, handleBorderPaint)
            canvas.drawCircle(drawRect.right.toFloat(), drawRect.bottom.toFloat(), r, handlePaint)
            canvas.drawCircle(drawRect.right.toFloat(), drawRect.bottom.toFloat(), r, handleBorderPaint)

            // Draw name
            selectedLabel?.let { label ->
                val padding = 12f
                val textWidth = labelPaint.measureText(label)
                val textHeight = labelPaint.textSize

                val bgTop = (drawRect.top - textHeight - padding * 2).coerceAtLeast(0f)
                val bgRight = (drawRect.left + textWidth + padding * 2).coerceAtMost(width.toFloat())

                canvas.drawRect(
                    drawRect.left.toFloat(),
                    bgTop,
                    bgRight,
                    bgTop + textHeight + padding * 2,
                    labelBgPaint
                )

                canvas.drawText(
                    label,
                    drawRect.left + padding,
                    bgTop + textHeight + padding / 2,
                    labelPaint
                )
            }
        }

                // Close button is rendered by Compose DesignModeButton cleanly at getStopButtonRect()
    }
}
