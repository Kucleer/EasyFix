<template>
  <div class="words">
    <PageHeading title="让单词，慢慢熟悉起来" description="温习、默写与整理，找到适合自己的记忆节奏。" />
    <el-card>
      <template #header>
        <div class="card-header">
          <span>单词本</span>
          <div>
            <el-button type="primary" @click="showAddDialog">
              <el-icon><Plus /></el-icon>
              新增单词
            </el-button>
            <el-button type="info" @click="showImportDialog">
              <el-icon><Upload /></el-icon>
              导入单词
            </el-button>
            <el-button type="success" @click="startReview">
              <el-icon><Edit /></el-icon>
              开始复习
            </el-button>
            <el-button type="warning" @click="showPrintDialog">
              <el-icon><Printer /></el-icon>
              打印默写
            </el-button>
            <el-button @click="startAnnotate">
              标注词组重点
            </el-button>
          </div>
        </div>
      </template>

      <!-- 单词 / 词组 统计（后端未返回 by_type 时不显示） -->
      <div v-if="typeStats" class="type-stats">
        <div v-for="item in typeStats" :key="item.key" class="type-stat">
          <span class="type-stat-name">{{ item.label }}</span>
          <span class="type-stat-num">{{ item.total }} 条</span>
          <span class="type-stat-acc">正确率 {{ item.accuracyText }}</span>
        </div>
      </div>

      <!-- 筛选条件 -->
      <div class="filters">
        <el-input
          v-model="filters.keyword"
          placeholder="搜索单词"
          clearable
          @change="fetchWords"
          style="width: 180px"
        />
        <el-select v-model="filters.grade" placeholder="年级" clearable @change="fetchWords" style="width: 120px">
          <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
        </el-select>
        <el-select v-model="filters.semester" placeholder="学期" clearable @change="fetchWords" style="width: 100px">
          <el-option label="上学期" :value="1" />
          <el-option label="下学期" :value="2" />
        </el-select>
        <el-select v-model="filters.tag_id" placeholder="标签" clearable @change="fetchWords" style="width: 150px">
          <el-option v-for="t in allTags" :key="t.id" :label="t.name" :value="t.id" />
        </el-select>
        <el-select v-model="filters.entry_type" placeholder="类型" clearable @change="onTypeFilterChange" style="width: 110px">
          <el-option label="单词" value="word" />
          <el-option label="词组" value="phrase" />
        </el-select>
        <el-select v-model="filters.focus_status" placeholder="标注状态" clearable @change="onTypeFilterChange" style="width: 130px">
          <el-option v-for="(label, key) in FOCUS_STATUS_LABELS" :key="key" :label="label" :value="key" />
        </el-select>
      </div>

      <!-- 正确率等级快速筛选 -->
      <div class="accuracy-level-filter" style="margin-top: 10px">
        <el-tag
          v-for="level in accuracyLevelOptions"
          :key="level.value"
          :type="filters.accuracy_level === level.value ? 'primary' : 'info'"
          class="accuracy-level-tag"
          @click="toggleAccuracyLevel(level.value)"
          style="cursor: pointer; margin-right: 8px"
        >
          {{ level.label }}
        </el-tag>
      </div>

      <!-- 单词列表 -->
      <el-table
        ref="tableRef"
        :data="words.items"
        stripe
        style="width: 100%; margin-top: 20px"
        @selection-change="handleSelectionChange"
        @sort-change="handleSortChange"
      >
        <el-table-column type="selection" width="55" />
        <el-table-column prop="english" label="英文" width="260">
          <template #default="{ row }">
            <div class="word-cell">
              <span class="word-english">{{ row.english }}</span>
              <template v-if="row.entry_type === 'phrase'">
                <el-tag size="small" type="warning" class="phrase-tag">词组</el-tag>
                <el-tag size="small" :type="focusStatusTagType(row.focus_status)" class="phrase-tag">{{ FOCUS_STATUS_LABELS[row.focus_status] || '未标注' }}</el-tag>
              </template>
              <el-button class="audio-btn-table" @click.stop="playWordAudio(row.id)" :loading="audioLoading" circle>
                <span v-if="!audioLoading">🔊</span>
              </el-button>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="chinese" label="中文" min-width="200" />
        <el-table-column prop="phonetic" label="音标" width="150">
          <template #default="{ row }">
            <span class="phonetic">{{ row.phonetic || '-' }}</span>
          </template>
        </el-table-column>
        <el-table-column label="属性" width="150">
          <template #default="{ row }">
            <el-tag v-if="row.grade" :style="{ fontSize: '14px' }">{{ row.grade }}年级</el-tag>
          </template>
        </el-table-column>
        <el-table-column label="复习" width="100">
          <template #default="{ row }">
            <span class="review-info">
              <span class="correct">{{ row.correct_count || 0 }}</span> /
              <span class="total">{{ row.review_count || 0 }}</span>
            </span>
          </template>
        </el-table-column>
        <el-table-column label="正确率" width="120" sortable prop="accuracy">
          <template #default="{ row }">
            <span :style="{ color: getAccuracyColor(row) }">{{ getAccuracyText(row) }}</span>
            <el-tag v-if="row.accuracy_level" :type="getAccuracyLevelTagType(row.accuracy_level)" :style="{ marginLeft: '5px', fontSize: '14px' }">
              {{ getAccuracyLevelText(row.accuracy_level) }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160" fixed="right"><template #default="{ row }"><ListActions :primary="{ label: '查看', run: () => viewDetail(row), disabled: false, danger: false }" :actions="[{ label: '编辑', run: () => editWord(row), disabled: false, danger: false },{ label: '删除', run: () => deleteWord(row), disabled: false, danger: true }]" /></template></el-table-column>
      </el-table>

      <!-- 分页 -->
      <div class="pagination">
        <el-pagination
          v-model:current-page="pagination.page"
          v-model:page-size="pagination.limit"
          :page-sizes="[10, 20, 50, 100]"
          :total="words.total"
          layout="total, sizes, prev, pager, next"
          @change="fetchWords"
        />
      </div>
    </el-card>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="dialogVisible" :title="dialogTitle" width="500px">
      <el-form :model="form" label-width="80px">
        <el-form-item label="英文" required>
          <el-input v-model="form.english" placeholder="输入英文单词" />
        </el-form-item>
        <el-form-item label="中文" required>
          <el-input v-model="form.chinese" placeholder="输入中文释义" />
        </el-form-item>
        <el-form-item label="音标">
          <el-input v-model="form.phonetic" placeholder="输入音标（可选）" />
        </el-form-item>
        <el-form-item label="年级">
          <el-select v-model="form.grade" placeholder="选择年级" clearable style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="学期">
          <el-select v-model="form.semester" placeholder="选择学期" clearable style="width: 100%">
            <el-option label="上学期" :value="1" />
            <el-option label="下学期" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="form.tag_ids" multiple placeholder="选择标签" style="width: 100%">
            <el-option v-for="t in allTags" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="saveWord">保存</el-button>
      </template>
    </el-dialog>

    <!-- 详情弹窗 -->
    <el-dialog v-model="detailVisible" title="单词详情" width="600px" class="detail-dialog">
      <el-tabs v-if="detailVisible" v-model="activeTab">
        <el-tab-pane label="基本信息" name="info">
          <el-form label-width="80px" size="default">
            <el-form-item label="英文">
              {{ detailWord.english }}
              <el-button class="audio-btn" @click="playWordAudio(detailWord.id)" :loading="audioLoading" size="small">🔊</el-button>
            </el-form-item>
            <el-form-item label="中文">{{ detailWord.chinese }}</el-form-item>
            <el-form-item label="音标">{{ detailWord.phonetic || '-' }}</el-form-item>
            <el-form-item label="年级">{{ detailWord.grade ? detailWord.grade + '年级' : '-' }}</el-form-item>
            <el-form-item label="学期">{{ detailWord.semester === 1 ? '上学期' : detailWord.semester === 2 ? '下学期' : '-' }}</el-form-item>
            <el-form-item label="标签">
              <el-tag v-for="t in detailWord.tags" :key="t.id" style="margin-right: 5px">{{ t.name }}</el-tag>
              <span v-if="!detailWord.tags || detailWord.tags.length === 0">-</span>
            </el-form-item>
            <el-form-item label="复习次数">{{ detailWord.review_count || 0 }}</el-form-item>
            <el-form-item label="正确次数">{{ detailWord.correct_count || 0 }}</el-form-item>
            <el-form-item label="正确率">{{ getAccuracyText(detailWord) }}</el-form-item>
          </el-form>
        </el-tab-pane>
        <el-tab-pane v-if="detailWord.entry_type === 'phrase'" label="词组重点" name="focus">
          <div class="focus-status-line">
            当前状态：<el-tag size="small" :type="focusStatusTagType(detailWord.focus_status)">{{ FOCUS_STATUS_LABELS[detailWord.focus_status] || '未标注' }}</el-tag>
          </div>
          <PhraseFocusEditor :word="detailWord" @saved="onFocusSaved" />
        </el-tab-pane>
        <el-tab-pane label="记忆曲线" name="curve">
          <div v-if="memoryCurve" class="memory-curve">
            <!-- 阶段进度条 -->
            <div class="phase-bar">
              <div class="phase-track">
                <div
                  class="phase-dot"
                  v-for="(phase, idx) in ['新学', '在途', '遗忘点', '牢记']"
                  :key="phase"
                  :class="{ active: memoryCurve.learning_phase === phase }"
                  :style="{ left: phasePosition[phase] + '%', borderColor: memoryCurve.learning_phase === phase ? phaseColors[phase] : '#ddd' }"
                >
                  {{ phase }}
                </div>
              </div>
            </div>

            <!-- 下次复习时间 -->
            <div class="next-review">
              <span v-if="memoryCurve.learning_phase === '遗忘点'">即将到期</span>
              <span v-else-if="memoryCurve.next_review_at">下次复习：{{ formatDate(memoryCurve.next_review_at) }}</span>
              <span v-else>暂未安排复习</span>
            </div>

            <!-- 复习历史 -->
            <div class="review-history">
              <div class="history-title">复习历史：</div>
              <div v-if="memoryCurve.review_history.length === 0" class="history-empty">暂无复习记录</div>
              <div v-else class="history-item">
                <span class="history-date">今天（待复习）</span>
              </div>
              <div v-for="(log, idx) in memoryCurve.review_history" :key="idx" class="history-item">
                <span class="history-date">{{ formatDate(log.reviewed_at) }}</span>
                <span v-if="log.is_correct" class="history-correct">正确</span>
                <span v-else class="history-wrong">错误 【{{ log.user_answer }}】</span>
              </div>
            </div>
          </div>
          <div v-else class="no-curve">加载中...</div>
        </el-tab-pane>
      </el-tabs>
      <template #footer>
        <el-button @click="detailVisible = false">关闭</el-button>
      </template>
    </el-dialog>

    <!-- 复习弹窗 -->
    <el-dialog v-model="reviewVisible" title="单词复习" width="1200px" :close-on-click-modal="false" class="review-dialog">
      <div v-if="reviewStep === 'config'" class="review-config">
        <el-form-item label="复习数量">
          <el-input-number v-model="reviewConfig.count" :min="10" :max="50" />
        </el-form-item>
        <el-form-item label="年级筛选">
          <el-select v-model="reviewConfig.grade" placeholder="全部" clearable style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="题型">
          <el-radio-group v-model="reviewConfig.type">
            <el-radio :value="1">默写英文</el-radio>
            <el-radio :value="2">选择中文</el-radio>
            <el-radio :value="3">听力</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="范围">
          <el-radio-group v-model="reviewConfig.entry_type">
            <el-radio value="">全部</el-radio>
            <el-radio value="word">只练单词</el-radio>
            <el-radio value="phrase">只练词组</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="reviewConfig.type === 1" label="词组档位">
          <el-radio-group v-model="reviewConfig.dictation_level">
            <el-radio :value="0">自动</el-radio>
            <el-radio :value="1">重点</el-radio>
            <el-radio :value="2">提示</el-radio>
            <el-radio :value="3">完整</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-button type="primary" @click="startReviewGame" :disabled="reviewStarting" style="width: 100%">开始复习</el-button>
      </div>

      <div v-else-if="reviewStep === 'question'" class="review-question">
        <div class="question-header">
          <span class="progress">{{ currentIndex + 1 }} / {{ reviewQuestions.length }}</span>
          <span class="timer">用时: {{ Math.floor(reviewElapsed / 60) }}:{{ String(reviewElapsed % 60).padStart(2, '0') }}</span>
        </div>

        <div class="question-content">
          <!-- 默写模式：显示中文 + 喇叭按钮 + 字母格输入 -->
          <div v-if="reviewConfig.type === 1" class="dictation">
            <div class="chinese" :style="{ fontSize: chineseFontSize }">
              {{ currentQuestion.chinese }}
            </div>
            <div class="audio-row">
              <el-button class="audio-btn" @click="playWordAudio(currentQuestion.word_id)" :loading="audioLoading" :disabled="dictationSpeakerDisabled">🔊</el-button>
            </div>
            <div class="hint-box">
              <div class="hint">{{ dictationHint }}</div>
            </div>
            <DictationInput
              ref="dictationInputRef"
              :question="currentQuestion"
              :disabled="currentQuestion.correct !== undefined"
              :result="currentQuestion.correct === undefined ? null : { tokenResults: currentQuestion.tokenResults, correct: currentQuestion.correct }"
              v-model="answers"
              @submit="submitAnswer"
            />
          </div>

          <!-- 选择模式：显示英文 + 喇叭按钮 -->
          <div v-else-if="reviewConfig.type === 2" class="choice">
            <div class="english">
              {{ currentQuestion.english }}
              <el-button class="audio-btn" @click="playWordAudio(currentQuestion.word_id)" :loading="audioLoading">🔊</el-button>
            </div>
            <el-radio-group v-model="selectedOption" @change="submitAnswer">
              <el-radio v-for="(opt, idx) in currentQuestion.options" :key="idx" :value="opt" :disabled="currentQuestion.correct !== undefined">
                {{ opt }}
              </el-radio>
            </el-radio-group>
          </div>

          <!-- 听力模式：仅喇叭按钮 + 输入框 -->
          <div v-else class="listening">
            <div class="audio-controls">
              <el-button @click="playWordAudio(currentQuestion.word_id)" :loading="audioLoading" class="audio-btn-large" type="primary" size="large">
                🔊 播放发音
              </el-button>
              <el-button @click="playWordAudio(currentQuestion.word_id)" :loading="audioLoading" class="audio-btn-replay" size="small">
                重播
              </el-button>
            </div>
            <div class="hint-box">
              <div class="hint">提示：{{ currentQuestion.word_length }}个字母</div>
            </div>
            <el-input
              ref="answerInputRef"
              v-model="userAnswer"
              placeholder="输入听到的英文单词"
              @keyup.enter="submitAnswer"
              :disabled="currentQuestion.correct !== undefined"
              class="answer-input"
            />
          </div>
        </div>

        <div class="question-actions">
          <el-button type="danger" @click="terminateReview">终止答题</el-button>
          <el-button v-if="currentQuestion.correct === undefined" type="primary" @click="submitAnswer">提交</el-button>
          <el-button v-else type="success" @click="finishReview">完成</el-button>
        </div>
      </div>

      <div v-else-if="reviewStep === 'result'" class="review-result">
        <!-- 顶部统计区 -->
        <div class="result-header">
          <div class="accuracy-display">
            <div class="accuracy-big">{{ reviewResult.accuracy }}%</div>
            <div class="accuracy-label">正确率</div>
          </div>
          <div class="stats-panel">
            <div class="stat-item">
              <span class="stat-value">{{ reviewResult.total }}</span>
              <span class="stat-label">总题数</span>
            </div>
            <div class="stat-item correct">
              <span class="stat-value">{{ reviewResult.correct }}</span>
              <span class="stat-label">正确</span>
            </div>
            <div class="stat-item error">
              <span class="stat-value">{{ reviewResult.error }}</span>
              <span class="stat-label">错误</span>
            </div>
            <div class="stat-item">
              <span class="stat-value">{{ Math.floor(reviewResult.duration / 60) }}:{{ String(reviewResult.duration % 60).padStart(2, '0') }}</span>
              <span class="stat-label">用时</span>
            </div>
          </div>
        </div>

        <!-- 错误单词列表 -->
        <div v-if="reviewResult.error > 0" class="error-word-list">
          <div class="error-words-scroll">
            <div v-for="(q, idx) in reviewQuestions.filter(q => !q.correct)" :key="idx" class="error-word-item">
              <div class="correct-side">
                <span class="correct-en">
                  {{ q.english }}
                  <el-button class="audio-btn" @click="playWordAudio(q.word_id)" :loading="audioLoading" size="small">🔊</el-button>
                </span>
                <span class="correct-cn">{{ q.chinese }}</span>
              </div>
              <div class="wrong-side">
                <span class="wrong-tag">错误</span>
                <span class="wrong-answer">{{ q.userAnswer || '(未作答)' }}</span>
              </div>
            </div>
          </div>
        </div>

        <el-button type="primary" @click="reviewVisible = false" class="finish-btn">完成</el-button>
      </div>
    </el-dialog>

    <!-- 打印弹窗 -->
    <el-dialog v-model="printDialogVisible" title="打印默写" width="400px" class="print-dialog">
      <el-form :model="printForm" label-width="80px">
        <el-form-item label="单词数量">
          <el-input-number v-model="printForm.count" :min="5" :max="100" />
        </el-form-item>
        <el-form-item label="年级筛选">
          <el-select v-model="printForm.grade" placeholder="全部" clearable style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="词组档位">
          <el-radio-group v-model="printForm.dictation_level">
            <el-radio-button :value="1">重点</el-radio-button>
            <el-radio-button :value="2">提示</el-radio-button>
            <el-radio-button :value="3">完整</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="printDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="generatePrintPdf">生成PDF</el-button>
      </template>
    </el-dialog>

    <!-- 词组重点批量标注 -->
    <PhraseAnnotateDialog ref="annotateDialogRef" @finished="refreshAfterAnnotate" />

    <!-- 导入弹窗 -->
    <el-dialog v-model="importDialogVisible" title="导入单词" width="1100px" class="import-dialog">
      <el-form :model="importForm" label-width="100px">
        <el-form-item label="导入方式">
          <el-radio-group v-model="importForm.mode">
            <el-radio label="text">文本粘贴</el-radio>
            <el-radio label="file">文件上传</el-radio>
          </el-radio-group>
        </el-form-item>
        <el-form-item v-if="importForm.mode === 'text'" label="单词格式">
          <el-input
            v-model="importForm.text"
            type="textarea"
            :rows="6"
            placeholder="每行一个单词，格式：英文 中文（用空格分隔）
例如：
apple 苹果
banana 香蕉
orange 橙子"
            @input="onTextChange"
          />
        </el-form-item>
        <el-form-item v-else-if="importForm.mode === 'file'" label="上传文件">
          <el-upload
            ref="uploadRef"
            :auto-upload="false"
            :limit="1"
            accept=".txt,.csv"
            :on-change="handleFileChange"
          >
            <el-button>选择文件</el-button>
            <template #tip>
              <div class="el-upload__tip">支持 .txt 或 .csv 文件，每行一个单词，格式：英文 中文</div>
            </template>
          </el-upload>
        </el-form-item>


        <!-- 单词预览表格 -->
        <el-form-item v-if="importForm.parsedWords.length > 0" label="单词预览">
          <div class="words-preview">
            <el-table :data="importForm.parsedWords" border stripe size="small" max-height="300">
              <el-table-column prop="english" label="英文" width="150">
                <template #default="{ row }">
                  <el-input v-model="row.english" size="small" />
                </template>
              </el-table-column>
              <el-table-column prop="chinese" label="中文" min-width="150">
                <template #default="{ row }">
                  <el-input v-model="row.chinese" size="small" />
                </template>
              </el-table-column>
              <el-table-column prop="phonetic" label="音标" width="120">
                <template #default="{ row }">
                  <el-input v-model="row.phonetic" size="small" placeholder="可选" />
                </template>
              </el-table-column>
              <el-table-column label="操作" width="60" fixed="right">
                <template #default="{ $index }">
                  <el-button type="danger" size="small" link @click="importForm.parsedWords.splice($index, 1)">删除</el-button>
                </template>
              </el-table-column>
            </el-table>
            <div class="preview-summary">共 {{ importForm.parsedWords.length }} 个单词</div>
          </div>
        </el-form-item>

        <el-form-item label="默认年级">
          <el-select v-model="importForm.grade" placeholder="选择年级（可选）" clearable style="width: 100%">
            <el-option v-for="g in gradeOptions" :key="g.value" :label="g.label" :value="g.value" />
          </el-select>
        </el-form-item>
        <el-form-item label="默认学期">
          <el-select v-model="importForm.semester" placeholder="选择学期（可选）" clearable style="width: 100%">
            <el-option label="上学期" :value="1" />
            <el-option label="下学期" :value="2" />
          </el-select>
        </el-form-item>
        <el-form-item label="标签">
          <el-select v-model="importForm.tag_ids" multiple placeholder="选择标签（可选）" style="width: 100%">
            <el-option v-for="t in allTags" :key="t.id" :label="t.name" :value="t.id" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="importDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="importWords" :loading="importing">导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import PageHeading from '@/components/PageHeading.vue'
import DictationInput from '@/components/DictationInput.vue'
import PhraseFocusEditor from '@/components/PhraseFocusEditor.vue'
import PhraseAnnotateDialog from '@/components/PhraseAnnotateDialog.vue'
import { ref, reactive, onMounted, computed, nextTick } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus, Edit, Printer, Upload } from '@element-plus/icons-vue'
import { buildCells, blankTokenCount, judge, shouldPlayBeforeAnswer } from '@/composables/dictation'
import { wordApi } from '@/api/word'
import { questionApi } from '@/api/question'
import { motivationApi } from '@/api/motivation'
import { useAppConfigStore } from '@/stores/appConfig'

const route = useRoute()
const appConfigStore = useAppConfigStore()
const words = ref({ total: 0, items: [] })
const allTags = ref([])
const filters = reactive({
  keyword: '',
  grade: null,
  semester: null,
  tag_id: null,
  accuracy_level: null,
  entry_type: '',      // '' 全部 / 'word' / 'phrase'
  focus_status: '',    // '' 全部 / 'none' / 'draft' / 'confirmed'
  sort_by: null,
  sort_order: 'desc',
})
const pagination = reactive({
  page: 1,
  limit: 20,
})

const dialogVisible = ref(false)
const dialogTitle = ref('新增单词')
const isEdit = ref(false)
const currentWordId = ref(null)

const form = reactive({
  english: '',
  chinese: '',
  phonetic: '',
  grade: null,
  semester: null,
  tag_ids: [],
})

const gradeOptions = [
  { label: '一年级', value: 1 },
  { label: '二年级', value: 2 },
  { label: '三年级', value: 3 },
  { label: '四年级', value: 4 },
  { label: '五年级', value: 5 },
  { label: '六年级', value: 6 },
  { label: '初一', value: 7 },
  { label: '初二', value: 8 },
  { label: '初三', value: 9 },
  { label: '高一', value: 10 },
  { label: '高二', value: 11 },
  { label: '高三', value: 12 },
]

// 正确率等级选项
const accuracyLevelOptions = ref([
  { label: '全部', value: null },
  { label: '新词', value: 'new' },
  { label: '需加强', value: 'weak' },
  { label: '薄弱', value: 'learning' },
  { label: '一般', value: 'good' },
  { label: '掌握', value: 'mastered' },
])

// 词组标注状态的中文名与标签颜色
const FOCUS_STATUS_LABELS = { none: '未标注', draft: '待确认', confirmed: '已确认' }
const focusStatusTagType = (status) =>
  status === 'confirmed' ? 'success' : status === 'draft' ? 'warning' : 'info'

// 类型/标注状态筛选变化：回到第一页重新查询
const onTypeFilterChange = () => {
  pagination.page = 1
  fetchWords()
}

// 切换正确率等级筛选
const toggleAccuracyLevel = (level) => {
  if (filters.accuracy_level === level) {
    filters.accuracy_level = null
  } else {
    filters.accuracy_level = level
  }
  pagination.page = 1
  fetchWords()
}

// 复习相关
const reviewVisible = ref(false)
const reviewStarting = ref(false) // 防止重复点击开始复习
const reviewStep = ref('config')
const reviewConfig = reactive({
  count: 20,
  grade: appConfigStore.defaultGrade,
  type: 1,
  entry_type: '',        // '' 全部 / 'word' 只练单词 / 'phrase' 只练词组
  dictation_level: 0,    // 0 自动 / 1 重点 / 2 提示 / 3 完整
})
const reviewQuestions = ref([])
const currentIndex = ref(0)
const userAnswer = ref('')
const answers = ref([])              // 默写各格内容，供 judge 使用
const dictationInputRef = ref(null)  // 默写组件引用
const autoPlayToken = ref(0)
const selectedOption = ref('')
const currentSessionId = ref(null)
const audioLoading = ref(false)
const reviewResult = reactive({
  total: 0,
  correct: 0,
  error: 0,
  accuracy: 0,
  duration: 0,
})

// 复习计时器
const reviewStartTime = ref(null)
const reviewTimer = ref(null)
const reviewElapsed = ref(0) // 秒
const answerInputRef = ref(null)

// 默写提示文字：有 tokens 时提示词数，否则提示字母数
const dictationHint = computed(() => {
  const q = currentQuestion.value
  if (!q) return ''
  if (Array.isArray(q.tokens) && q.tokens.length > 0) {
    return `提示：${blankTokenCount(q)}个词`
  }
  return `提示：${buildCells(q).filter(c => !c.fixed).length}个字母`
})

// 重点/提示档词组：作答前不发音，此时喇叭按钮禁用，提交后才可点
const dictationSpeakerDisabled = computed(() => {
  const q = currentQuestion.value
  if (!q || reviewConfig.type !== 1) return false
  return !shouldPlayBeforeAnswer(q, reviewConfig.type) && q.correct === undefined
})

// 长中文自适应字号，避免溢出
const chineseFontSize = computed(() => {
  const len = (currentQuestion.value?.chinese || '').length
  if (len <= 6) return '64px'
  if (len <= 10) return '48px'
  if (len <= 16) return '36px'
  if (len <= 24) return '28px'
  if (len <= 36) return '22px'
  return '18px'
})

// 打印相关
const printDialogVisible = ref(false)
const printForm = reactive({
  count: 25,
  grade: appConfigStore.defaultGrade,
  dictation_level: 1,   // 词组档位：1 重点 / 2 提示 / 3 完整
})

// 导入相关
const importDialogVisible = ref(false)
const importing = ref(false)
const uploadRef = ref()
const importForm = reactive({
  mode: 'text',
  text: '',
  file: null,
  parsedWords: [],  // 解析后的单词预览
  grade: appConfigStore.defaultGrade,
  semester: appConfigStore.defaultSemester,
  tag_ids: [],
})

const currentQuestion = ref({})
const tableRef = ref()
const selectedWords = ref([])

// 记忆曲线相关
const memoryCurve = ref(null)
const memoryCurveLoading = ref(false)

const fetchMemoryCurve = async (wordId) => {
  memoryCurveLoading.value = true
  try {
    const { data } = await wordApi.getMemoryCurve(wordId)
    memoryCurve.value = data
  } catch (error) {
    console.error('获取记忆曲线失败:', error)
  } finally {
    memoryCurveLoading.value = false
  }
}

// 阶段对应的颜色
const phaseColors = {
  '新学': '#909399',
  '在途': '#409eff',
  '遗忘点': '#e6a23c',
  '牢记': '#67c23a'
}

// 阶段对应的进度位置
const phasePosition = {
  '新学': 12.5,
  '在途': 37.5,
  '遗忘点': 62.5,
  '牢记': 87.5
}

// 格式化日期
const formatDate = (dateStr) => {
  if (!dateStr) return ''
  const date = new Date(dateStr)
  const month = date.getMonth() + 1
  const day = date.getDate()
  return `${month}月${day}日`
}

// 详情弹窗相关
const detailVisible = ref(false)
const detailWord = ref({})
const activeTab = ref('info')

// 词组重点保存成功：同步详情弹窗内的数据并刷新列表
const onFocusSaved = (updated) => {
  if (updated && updated.id === detailWord.value.id) {
    detailWord.value = { ...detailWord.value, ...updated }
  }
  fetchWords()
}

const viewDetail = async (row) => {
  detailWord.value = row
  activeTab.value = 'info'
  memoryCurve.value = null
  detailVisible.value = true
  // 获取记忆曲线
  await fetchMemoryCurve(row.id)
}

// 计算单词正确率
const getAccuracy = (row) => {
  if (!row.review_count || row.review_count === 0) return 0
  return (row.correct_count / row.review_count) * 100
}

// 获取正确率显示文本
const getAccuracyText = (row) => {
  if (!row.review_count || row.review_count === 0) return '--'
  return getAccuracy(row).toFixed(0) + '%'
}

// 获取正确率颜色（100%绿色，0%红色，渐变）
const getAccuracyColor = (row) => {
  if (!row.review_count || row.review_count === 0) return '#909399'
  const accuracy = getAccuracy(row)
  if (accuracy >= 100) return '#67c23a'  // 绿色
  if (accuracy <= 0) return '#f56c6c'    // 红色
  // 渐变色：从红到黄到绿
  if (accuracy < 50) {
    // 红到黄
    const ratio = accuracy / 50
    const r = 245
    const g = Math.round(67 + (183 - 67) * ratio)
    const b = Math.round(108 + (58 - 108) * ratio)
    return `rgb(${r}, ${g}, ${b})`
  } else {
    // 黄到绿
    const ratio = (accuracy - 50) / 50
    const r = Math.round(245 - (245 - 103) * ratio)
    const g = Math.round(183 + (194 - 183) * ratio)
    const b = Math.round(58 + (58 - 58) * ratio)
    return `rgb(${r}, ${g}, ${b})`
  }
}

// 获取正确率等级文字
const getAccuracyLevelText = (level) => {
  const map = {
    'new': '新词',
    'weak': '需加强',
    'learning': '薄弱',
    'good': '一般',
    'mastered': '掌握',
  }
  return map[level] || level
}

// 获取正确率等级标签类型
const getAccuracyLevelTagType = (level) => {
  const map = {
    'new': 'info',
    'weak': 'danger',
    'learning': 'warning',
    'good': '',
    'mastered': 'success',
  }
  return map[level] || 'info'
}

// 处理表格排序变化（使用后端排序）
const handleSortChange = ({ prop, order }) => {
  if (!prop) {
    // 取消排序
    filters.sort_by = null
    filters.sort_order = 'desc'
  } else if (prop === 'accuracy') {
    // 正确率排序需要后端处理
    filters.sort_by = 'accuracy'
    filters.sort_order = order === 'ascending' ? 'asc' : 'desc'
  } else {
    // 其他字段使用后端排序
    filters.sort_by = prop
    filters.sort_order = order === 'ascending' ? 'asc' : 'desc'
  }
  pagination.page = 1 // 重置到第一页
  fetchWords()
}

const fetchWords = async () => {
  try {
    const params = {
      skip: (pagination.page - 1) * pagination.limit,
      limit: pagination.limit,
    }
    if (filters.keyword) params.keyword = filters.keyword
    if (filters.grade) params.grade = filters.grade
    if (filters.semester) params.semester = filters.semester
    if (filters.tag_id) params.tag_ids = filters.tag_id
    if (filters.accuracy_level) params.accuracy_level = filters.accuracy_level
    if (filters.entry_type) params.entry_type = filters.entry_type
    if (filters.focus_status) params.focus_status = filters.focus_status
    if (filters.sort_by) {
      params.sort_by = filters.sort_by
      params.sort_order = filters.sort_order
    }

    const { data } = await wordApi.list(params)
    words.value = data
  } catch (error) {
    ElMessage.error('获取单词列表失败')
  }
}

const fetchTags = async () => {
  try {
    const { data } = await questionApi.listTags()
    allTags.value = data
  } catch (error) {
    console.error('获取标签失败:', error)
  }
}

const showAddDialog = () => {
  dialogTitle.value = '新增单词'
  isEdit.value = false
  resetForm()
  dialogVisible.value = true
}

const editWord = (row) => {
  dialogTitle.value = '编辑单词'
  isEdit.value = true
  currentWordId.value = row.id
  form.english = row.english
  form.chinese = row.chinese
  form.phonetic = row.phonetic || ''
  form.grade = row.grade
  form.semester = row.semester
  form.tag_ids = row.tags ? row.tags.map(t => t.id) : []
  dialogVisible.value = true
}

const resetForm = () => {
  form.english = ''
  form.chinese = ''
  form.phonetic = ''
  form.grade = appConfigStore.defaultGrade
  form.semester = appConfigStore.defaultSemester
  form.tag_ids = []
}

const saveWord = async () => {
  if (!form.english || !form.chinese) {
    ElMessage.warning('请填写必填项')
    return
  }

  try {
    if (isEdit.value) {
      await wordApi.update(currentWordId.value, form)
      ElMessage.success('更新成功')
    } else {
      await wordApi.create(form)
      ElMessage.success('创建成功')
    }
    dialogVisible.value = false
    fetchWords()
  } catch (error) {
    ElMessage.error('保存失败')
  }
}

const deleteWord = async (row) => {
  try {
    await ElMessageBox.confirm('确定删除该单词吗？', '提示', {
      confirmButtonText: '确定',
      cancelButtonText: '取消',
      type: 'warning',
    })
    await wordApi.delete(row.id)
    ElMessage.success('删除成功')
    fetchWords()
  } catch (error) {
    if (error !== 'cancel') {
      ElMessage.error('删除失败')
    }
  }
}

// 复习
const startReview = () => {
  reviewStep.value = 'config'
  // 如果有选中单词，默认数量为选中数量
  if (selectedWords.value.length > 0) {
    reviewConfig.count = selectedWords.value.length
  }
  reviewVisible.value = true
}

const handleSelectionChange = (selection) => {
  selectedWords.value = selection
}

const startReviewGame = async () => {
  if (reviewStarting.value) return
  reviewStarting.value = true
  try {
    const params = {
      count: reviewConfig.count,
    }
    if (reviewConfig.grade) params.grade = reviewConfig.grade
    // 范围：非默认时传 entry_type（只练单词/词组）
    if (reviewConfig.entry_type) params.entry_type = reviewConfig.entry_type
    // 词组档位：仅默写（type 1）且手动选档（非0）时传 dictation_level，选择/听力题型忽略残留的档位
    if (reviewConfig.type === 1 && reviewConfig.dictation_level) params.dictation_level = reviewConfig.dictation_level
    // 如果有选中单词，传递单词ID列表
    if (selectedWords.value.length > 0) {
      params.word_ids = selectedWords.value.map(w => w.id).join(',')
    }

    const { data } = await wordApi.startReview(params)
    reviewQuestions.value = data.questions.map(q => ({
      ...q,
      correct: undefined,
    }))
    currentSessionId.value = data.session_id
    // 进入第一题前先作废可能残留的重播，避免静音题期间播放旧音频
    autoPlayToken.value++
    currentIndex.value = 0
    userAnswer.value = ''
    selectedOption.value = ''
    currentQuestion.value = reviewQuestions.value[0]
    reviewStep.value = 'question'
    if (reviewConfig.type === 1) {
      // 组件会随题目变化自动重置，这里挂载后再聚焦并复位光标
      nextTick(() => {
        dictationInputRef.value?.reset()
        setTimeout(() => dictationInputRef.value?.focus(), 100)
      })
    }

    // 听力固定自动播放；默写仅在作答前应发音时播放（播完停3秒再播一次）
    const firstQ = reviewQuestions.value[0]
    if (reviewConfig.type === 3 || (reviewConfig.type === 1 && shouldPlayBeforeAnswer(firstQ, reviewConfig.type))) {
      setTimeout(() => autoPlayWithReplay(firstQ.word_id), 400)
    }

    // 启动计时器 - 先清除可能存在的旧计时器
    if (reviewTimer.value) {
      clearInterval(reviewTimer.value)
    }
    reviewStartTime.value = Date.now()
    reviewElapsed.value = 0
    reviewTimer.value = setInterval(() => {
      reviewElapsed.value = Math.floor((Date.now() - reviewStartTime.value) / 1000)
    }, 1000)
  } catch (error) {
    ElMessage.error('获取复习内容失败')
  } finally {
    reviewStarting.value = false
  }
}

// 播放单词音频（Promise 在播放结束/失败时 resolve）
const playWordAudio = async (wordId) => {
  if (!wordId) return
  audioLoading.value = true

  try {
    const response = await fetch(`/api/words/${wordId}/audio`)
    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`)
    }

    const blob = await response.blob()
    const audioUrl = URL.createObjectURL(blob)
    const audio = new Audio(audioUrl)

    await new Promise((resolve) => {
      audio.onended = () => {
        audioLoading.value = false
        URL.revokeObjectURL(audioUrl)
        resolve()
      }
      audio.onerror = () => {
        audioLoading.value = false
        URL.revokeObjectURL(audioUrl)
        ElMessage.warning('单词音频无法解码，请重试')
        resolve()
      }
      audio.play().catch((error) => {
        audioLoading.value = false
        URL.revokeObjectURL(audioUrl)
        console.error('音频播放失败:', error)
        ElMessage.warning('浏览器未能播放单词音频，请点击喇叭重试')
        resolve()
      })
    })
  } catch (e) {
    console.error('音频播放失败:', e)
    ElMessage.warning('音频播放失败')
    audioLoading.value = false
  }
}

// 进入新题时：自动播放，暂停3秒后再播一次
const autoPlayWithReplay = async (wordId) => {
  if (!wordId) return
  const token = ++autoPlayToken.value
  await playWordAudio(wordId)
  if (autoPlayToken.value !== token) return
  await new Promise(r => setTimeout(r, 3000))
  if (autoPlayToken.value !== token) return
  await playWordAudio(wordId)
}

const submitAnswer = () => {
  const q = currentQuestion.value
  if (reviewConfig.type === 1) {
    // 默写：用 judge 按词（或整条）判对
    const res = judge(q, answers.value)
    q.correct = res.correct
    q.userAnswer = res.userAnswer
    q.tokenResults = res.tokenResults
    userAnswer.value = res.userAnswer
    // 重点/提示档词组作答前不发音，提交后补播一次
    if (!shouldPlayBeforeAnswer(q, reviewConfig.type)) {
      playWordAudio(q.word_id)
    }
  } else if (reviewConfig.type === 3) {
    // 听力：比较英文输入
    q.correct = userAnswer.value.toLowerCase().trim() === q.english.toLowerCase().trim()
    q.userAnswer = userAnswer.value
  } else {
    // 选择
    q.correct = selectedOption.value === q.chinese
    q.userAnswer = selectedOption.value
  }
  // 显示toast提示
  if (q.correct) {
    ElMessage({ message: '✓ 正确', type: 'success', duration: 3000, showClose: false, customClass: 'toast-large' })
  } else {
    ElMessage({
      message: `✗ 错误 - 正确答案: ${q.english}`,
      type: 'error',
      duration: 3000,
      showClose: false,
      customClass: 'toast-large',
    })
  }
  // 显示答案后自动进入下一题
  if (currentIndex.value < reviewQuestions.value.length - 1) {
    setTimeout(() => {
      nextQuestion()
    }, 1500)
  }
}

const nextQuestion = () => {
  // 进入任意题目都先作废上一题待执行的重播，静音题不会调用 autoPlayWithReplay，否则无法取消
  autoPlayToken.value++
  currentIndex.value++
  currentQuestion.value = reviewQuestions.value[currentIndex.value]
  userAnswer.value = ''
  selectedOption.value = ''
  if (reviewConfig.type === 1) {
    // 组件随题目变化自动重置，这里复位光标并聚焦
    nextTick(() => {
      dictationInputRef.value?.reset()
      setTimeout(() => dictationInputRef.value?.focus(), 100)
    })
  }
  // 听力固定自动播放；默写仅在作答前应发音时播放
  if (reviewConfig.type === 3 || (reviewConfig.type === 1 && shouldPlayBeforeAnswer(currentQuestion.value, reviewConfig.type))) {
    setTimeout(() => autoPlayWithReplay(currentQuestion.value.word_id), 300)
  }
  setTimeout(() => {
    if (reviewConfig.type === 1) {
      dictationInputRef.value?.focus()
      return
    }
    const input = answerInputRef.value?.$el?.querySelector('input')
    if (input) {
      input.focus()
    } else {
      answerInputRef.value?.focus()
    }
  }, 100)
}

// 终止答题，结算已答题目
const terminateReview = async () => {
  try {
    await ElMessageBox.confirm('确定要终止答题吗？已答题目将按实际结果结算。', '终止确认', {
      confirmButtonText: '确定终止',
      cancelButtonText: '继续答题',
      type: 'warning',
    })
    // 将未作答的题目标记为错误
    for (const q of reviewQuestions.value) {
      if (q.correct === undefined) {
        q.correct = false
      }
    }
    await finishReview()
  } catch (error) {
    // 用户取消，继续答题
  }
}

const finishReview = async () => {
  autoPlayToken.value++
  // 停止计时器
  if (reviewTimer.value) {
    clearInterval(reviewTimer.value)
    reviewTimer.value = null
  }
  const duration = reviewElapsed.value

  const results = reviewQuestions.value.map(q => {
    const r = {
      word_id: q.word_id,
      is_correct: q.correct,
      user_answer: q.userAnswer || '',
      review_type: reviewConfig.type,
      // 仅默写题型且手动选档时才算非自动，选择/听力忽略残留的档位
      dictation_auto: !(reviewConfig.type === 1 && reviewConfig.dictation_level !== 0),
    }
    // 题目带档位时回传档位
    if (q.dictation_level != null) r.dictation_level = q.dictation_level
    // 按词判对结果（无 tokens 时为 null，不回传）
    if (q.tokenResults != null) r.token_results = q.tokenResults
    return r
  })

  try {
    const { data } = await wordApi.submitReview({
      session_id: currentSessionId.value,
      results,
      duration,
    })
    reviewResult.total = data.total
    reviewResult.correct = data.correct
    reviewResult.error = data.error
    reviewResult.accuracy = data.accuracy
    reviewResult.duration = duration
    reviewStep.value = 'result'

    // 调用单词正确率成就检查
    try {
      await motivationApi.triggerWordAccuracy({
        total_count: data.total,
        correct_count: data.correct,
        reason: '单词复习'
      })
    } catch (error) {
      console.error('激励触发失败:', error)
    }
  } catch (error) {
    ElMessage.error('提交结果失败')
  }
}

// 词组重点批量标注（由家长点击触发）
const annotateDialogRef = ref(null)
const startAnnotate = () => {
  annotateDialogRef.value?.start()
}
const refreshAfterAnnotate = () => {
  fetchWords()
  fetchTypeStats()
}

// 单词/词组分开统计；后端没有 by_type 时为 null，页面不显示
const typeStatsRaw = ref(null)
const typeStats = computed(() => {
  const by = typeStatsRaw.value
  if (!by || !by.word || !by.phrase) return null
  const fmt = (v) => (v === null || v === undefined ? '--' : `${Math.round(v * 10) / 10}%`)
  return [
    { key: 'word', label: '单词', total: by.word.total ?? 0, accuracyText: fmt(by.word.accuracy) },
    { key: 'phrase', label: '词组', total: by.phrase.total ?? 0, accuracyText: fmt(by.phrase.accuracy) },
  ]
})
const fetchTypeStats = async () => {
  try {
    const { data } = await wordApi.getStats()
    typeStatsRaw.value = data?.by_type || null
  } catch (error) {
    typeStatsRaw.value = null
  }
}

// 打印
const showPrintDialog = () => {
  printDialogVisible.value = true
}

const generatePrintPdf = async () => {
  try {
    const params = { count: printForm.count, dictation_level: printForm.dictation_level }
    if (printForm.grade) params.grade = printForm.grade

    const { data } = await wordApi.printPdf(params)
    window.open(data.pdf_url, '_blank')
    printDialogVisible.value = false
    ElMessage.success('PDF已生成')
  } catch (error) {
    ElMessage.error('生成PDF失败')
  }
}

// 导入
const showImportDialog = () => {
  importForm.mode = 'text'
  importForm.text = ''
  importForm.file = null
  importForm.parsedWords = []
  importForm.grade = null
  importForm.semester = null
  importForm.tag_ids = []
  importDialogVisible.value = true
}

const handleFileChange = (file) => {
  onFileChange(file)
}

// 文本模式变化时更新预览
const onTextChange = () => {
  if (importForm.mode === 'text' && importForm.text.trim()) {
    importForm.parsedWords = smartParseWords(importForm.text)
  }
}

// 文件模式变化时
const onFileChange = (file) => {
  importForm.file = file.raw
  if (file.raw) {
    const reader = new FileReader()
    reader.onload = e => {
      importForm.parsedWords = smartParseWords(e.target.result)
    }
    reader.readAsText(file.raw)
  }
}

// 智能分隔单词 - 自动识别英文和中文
const smartParseWords = (text) => {
  // 清理文本控制字符（保留\n\r）
  const cleaned = text
    .replace(/[\u0001-\u0009\u000B\u000C\u000E-\u001F\u007F-\u009F]/g, '') // 移除控制字符（保留\n\r即10和13）
    .replace(/['']/g, "'")  // 规范化撇号
    .replace(/[""]/g, '"')
    .replace(/（/g, '(').replace(/）/g, ')')  // 规范化中文括号
    .replace(/[ \t]+/g, ' ')   // 规范化空格（保留换行）

  const words = []

  // 按行分割
  const lines = cleaned.split('\n')

  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue

    // 分割本行的各个单词（按制表符或连续空格分割）
    // 格式如: "1.mess 杂乱  2.whose 谁的" 或 "1.mess 杂乱\t2.whose 谁的"
    const entries = trimmed.split(/(?:\t|  +)(?=\d+\.)/)

    for (const entry of entries) {
      if (!entry.trim()) continue

      // 去掉序号前缀，如 "1.mess" 或 "1. mess"
      let content = entry.replace(/^\d+\.?\s*/, '').trim()
      if (!content) continue

      let phonetic = ''
      let english = ''
      let chinese = ''

      // 先提取音标 /eɪ/ 或 [音标] 格式（可能在末尾或中间）
      // 提取末尾的 /音标/ 格式
      const phoneticMatch = content.match(/\/([^\/]+)\/$/)
      if (phoneticMatch) {
        phonetic = phoneticMatch[1]
        content = content.replace(/\/[^\/]+\/$/, '').trim()
      }
      // 提取 [音标] 格式
      const bracketPhonetic = content.match(/\[([^\]]+)\]/)
      if (bracketPhonetic) {
        phonetic = bracketPhonetic[1]
        content = content.replace(/\[[^\]]+\]/, '').trim()
      }

      // 去掉末尾的括号注释如 (复数)
      content = content.replace(/\s*\([^)]*\)\s*$/, '').trim()

      // 分离英文和中文
      // 格式1: 英文 + 空格 + 中文（如 "mess 杂乱" 或 "school bag 书包"）
      // 格式2: 只有英文或只有中文
      // 格式3: 英文 + 空格 + 音标（如 "baby /eɪ/"）

      // 尝试按空格分割
      const parts = content.split(/\s+/)

      if (parts.length >= 2) {
        // 检查第一部分是否是纯英文
        const firstPart = parts[0]
        const isEnglish = /^[a-zA-Z][a-zA-Z'-]*$/.test(firstPart) ||
                          /^[a-zA-Z][a-zA-Z'-]*(?:\s+[a-zA-Z][a-zA-Z'-]*)+$/.test(firstPart)

        if (isEnglish) {
          english = firstPart
          // 剩余部分是中文或其他
          const rest = parts.slice(1).join(' ').trim()
          if (rest) {
            // 检查是否是音标格式
            if (rest.startsWith('/') && rest.endsWith('/')) {
              phonetic = rest.slice(1, -1)
            } else {
              chinese = rest
            }
          }
        } else {
          // 第一部分不是纯英文，可能是中文
          chinese = content
        }
      } else if (parts.length === 1) {
        // 只有一个部分
        const part = parts[0]
        if (/^[a-zA-Z][a-zA-Z'-]*$/.test(part) || /^[a-zA-Z][a-zA-Z'-]*(?:\s+[a-zA-Z][a-zA-Z'-]*)+$/.test(part)) {
          // 纯英文
          english = part
        } else {
          // 纯中文
          chinese = part
        }
      }

      if (english || chinese) {
        words.push({
          english: english || '',
          chinese: chinese || '',
          phonetic: phonetic || '',
          original: entry
        })
      }
    }
  }

  return words
}

const parseTextToWords = (text) => {
  const lines = text.trim().split('\n')
  const words = []
  for (const line of lines) {
    const trimmed = line.trim()
    if (!trimmed) continue
    // 智能分隔
    const parsed = smartParseWords(trimmed)
    if (parsed.length > 0) {
      words.push(parsed[0])
    }
  }
  return words
}

const importWords = async () => {
  let words = []

  // 优先使用预览表格中的数据（用户可能已编辑）
  if (importForm.parsedWords && importForm.parsedWords.length > 0) {
    words = importForm.parsedWords.filter(w => w.english && w.chinese)
  } else if (importForm.mode === 'text') {
    if (!importForm.text.trim()) {
      ElMessage.warning('请输入单词内容')
      return
    }
    words = smartParseWords(importForm.text)
  } else if (importForm.mode === 'file') {
    if (!importForm.file) {
      ElMessage.warning('请选择文件')
      return
    }
    // 读取文件内容
    try {
      const reader = new FileReader()
      const fileContent = await new Promise((resolve, reject) => {
        reader.onload = e => resolve(e.target.result)
        reader.onerror = reject
        reader.readAsText(importForm.file)
      })
      words = smartParseWords(fileContent)
    } catch (error) {
      ElMessage.error('读取文件失败')
      return
    }
  }

  if (words.length === 0) {
    ElMessage.warning('未解析到有效单词')
    return
  }

  importing.value = true
  let successCount = 0
  let failCount = 0

  for (const word of words) {
    try {
      await wordApi.create({
        english: word.english,
        chinese: word.chinese,
        phonetic: word.phonetic || undefined,
        grade: importForm.grade,
        semester: importForm.semester,
        tag_ids: importForm.tag_ids,
      })
      successCount++
    } catch (error) {
      failCount++
    }
  }

  importing.value = false
  importDialogVisible.value = false

  ElMessage.success(`导入完成：成功 ${successCount} 个，失败 ${failCount} 个`)
  fetchWords()
}

onMounted(async () => {
  await appConfigStore.load()
  // 首页年级维度跳转：/words?grade=6
  const routeGrade = Number(route.query.grade)
  if (routeGrade) {
    filters.grade = routeGrade
  } else if (filters.grade == null) {
    filters.grade = appConfigStore.defaultGrade
  }
  if (filters.semester == null) filters.semester = appConfigStore.defaultSemester
  if (reviewConfig.grade == null) reviewConfig.grade = appConfigStore.defaultGrade
  if (printForm.grade == null) printForm.grade = appConfigStore.defaultGrade
  if (importForm.grade == null) importForm.grade = appConfigStore.defaultGrade
  if (importForm.semester == null) importForm.semester = appConfigStore.defaultSemester
  fetchWords()
  fetchTags()
  fetchTypeStats()
})
</script>

<style scoped>
.words  {

  max-width: 1400px;
  margin: 0 auto;
}

.card-header  {

  display: flex;
  justify-content: space-between;
  align-items: center;
}

.filters  {

  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.word-english  {

  font-weight: bold;
  color: var(--accent-blue);
  font-size: 16px;
}

.word-cell  {

  display: flex;
  align-items: center;
  gap: 8px;
}

.word-cell .word-english  {

  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.phonetic  {

  color: var(--text-muted);
  font-family: monospace;
}

.review-info .correct  {

  color: #67c23a;
  font-weight: bold;
}

.review-info .total  {

  color: var(--text-muted);
}

.pagination  {

  margin-top: 20px;
  display: flex;
  justify-content: flex-end;
}

/* 复习弹窗样式 */
:deep(.review-dialog)  {

  --review-scale: 1;
  transform: scale(var(--review-scale));
  transform-origin: center center;
}

:deep(.review-dialog .el-dialog__body)  {

  padding: 0;
}

/* 复习弹窗背景虚化 */
:deep(.el-overlay-dialog)  {

  backdrop-filter: blur(8px);
  background: rgba(0, 0, 0, 0.3) !important;
}

.review-config  {

  padding: 40px;
  font-size: 20px;
}

.review-question  {

  padding: 40px;
  display: flex;
  flex-direction: column;
  height: 70vh;
  max-height: 600px;
}

.question-header  {

  display: flex;
  justify-content: center;
  align-items: center;
  gap: 40px;
  margin-bottom: 30px;
  flex-shrink: 0;
  position: sticky;
  top: 0;
  background: #fff;
  z-index: 10;
  padding: 10px 0;
}

.progress  {

  font-size: 36px;
  font-weight: bold;
  color: var(--accent-blue);
}

.timer  {

  font-size: 32px;
  color: var(--text-muted);
  font-family: monospace;
  font-weight: 600;
}

.result-display  {

  text-align: center;
  padding: 24px 48px;
  border-radius: 16px;
  margin-bottom: 30px;
}

.correct-display  {

  background: linear-gradient(135deg, #67c23a 0%, #5daf34 100%);
  color: #fff;
}

.wrong-display  {

  background: linear-gradient(135deg, #f56c6c 0%, #e64242 100%);
  color: #fff;
}

.result-status  {

  font-size: 32px;
  font-weight: bold;
  margin-bottom: 8px;
}

.result-answer-large  {

  font-size: 36px;
  font-weight: bold;
}

.your-answer  {

  font-size: 24px;
  margin-top: 8px;
  opacity: 0.9;
}

.question-content  {

  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.dictation  {

  text-align: center;
  padding: 20px;
}

.dictation .chinese  {

  font-weight: bold;
  color: var(--text-primary);
  margin-bottom: 16px;
  letter-spacing: 4px;
  line-height: 1.45;
  word-break: break-word;
  overflow-wrap: anywhere;
  padding: 0 12px;
  max-width: 100%;
  box-sizing: border-box;
}

.dictation .audio-row  {

  margin-bottom: 12px;
}

.dictation .hint-box  {

  margin-bottom: 28px;
}

.dictation .hint  {

  font-size: 24px;
  color: var(--text-secondary);
  background: #f5f7fa;
  padding: 10px 28px;
  border-radius: 8px;
  display: inline-block;
  margin-bottom: 12px;
}

.dictation .answer-input  {

  max-width: 600px;
  margin: 0 auto;
}

.dictation .answer-input :deep(.el-input__wrapper)  {

  padding: 20px 30px;
  border-radius: 12px;
  border: 3px solid #dcdfe6;
  box-shadow: none;
  transition: all 0.3s;
}

.dictation .answer-input :deep(.el-input__wrapper.is-focus)  {

  border-color: var(--accent-blue);
  box-shadow: 0 0 0 4px rgba(64, 158, 255, 0.1);
}

.dictation .answer-input :deep(.el-input__inner)  {

  font-size: 48px;
  text-align: center;
  letter-spacing: 5px;
  height: 80px;
  line-height: 80px;
}

.result  {

  margin-top: 30px;
  padding: 16px 32px;
  border-radius: 12px;
  display: inline-block;
  font-size: 28px;
}

.result.correct-result  {

  background: #f0f9eb;
  color: #67c23a;
  border: 2px solid #67c23a;
}

.result.wrong-result  {

  background: #fef0f0;
  color: #f56c6c;
  border: 2px solid #f56c6c;
}

.correct-answer  {

  font-size: 28px;
  font-weight: bold;
}

.wrong-result .correct-answer  {

  color: #67c23a;
}

.correct-result .correct-answer  {

  color: var(--text-muted);
}

/* 答题正确动画 */
@keyframes correctPulse  {

  0%  {
   transform: scale(1);
   }
  50%  {
   transform: scale(1.05);
   }
  100%  {
   transform: scale(1);
   }
}

@keyframes correctGlow  {

  0%  {
   box-shadow: 0 0 0 0 rgba(103, 194, 58, 0.4);
   }
  50%  {
   box-shadow: 0 0 30px 10px rgba(103, 194, 58, 0.2);
   }
  100%  {
   box-shadow: 0 0 0 0 rgba(103, 194, 58, 0);
   }
}

.result.correct-result  {

  animation: correctPulse 0.5s ease-out, correctGlow 0.8s ease-out;
}

.result.correct-result .correct-answer  {

  color: #67c23a;
}

/* 答题错误动画 */
@keyframes wrongShake  {

  0%, 100%  {
   transform: translateX(0);
   }
  20%, 60%  {
   transform: translateX(-10px);
   }
  40%, 80%  {
   transform: translateX(10px);
   }
}

.result.wrong-result  {

  animation: wrongShake 0.5s ease-out;
}

.result.wrong-result .correct-answer  {

  color: #f56c6c;
}

.choice  {

  text-align: center;
}

.choice .english  {

  font-size: 64px;
  font-weight: bold;
  color: var(--accent-blue);
  margin-bottom: 50px;
}

.choice .el-radio-group  {

  display: flex;
  flex-direction: column;
  gap: 25px;
  align-items: center;
}

.choice .el-radio  {

  font-size: 28px;
  padding: 20px 40px;
  min-width: 400px;
}

.choice .el-radio .el-radio__label  {

  font-size: 28px;
}

/* 听力模式 */
.listening  {

  text-align: center;
  padding: 20px;
}

.listening .audio-controls  {

  margin-bottom: 40px;
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
}

.listening .audio-btn-large  {

  font-size: 32px;
  padding: 30px 60px;
}

.listening .audio-btn-replay  {

  font-size: 18px;
}

.listening .hint-box  {

  margin-bottom: 40px;
}

.listening .hint  {

  font-size: 28px;
  color: var(--text-secondary);
  background: #f5f7fa;
  padding: 12px 32px;
  border-radius: 8px;
  display: inline-block;
  margin-bottom: 20px;
}

.listening .answer-input  {

  max-width: 600px;
  margin: 0 auto;
}

.listening .answer-input :deep(.el-input__wrapper)  {

  border-radius: 12px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.1);
}

.listening .answer-input :deep(.el-input__wrapper.is-focus)  {

  box-shadow: 0 2px 12px rgba(64, 158, 255, 0.3);
}

.listening .answer-input :deep(.el-input__inner)  {

  font-size: 28px;
  text-align: center;
  letter-spacing: 8px;
  height: 60px;
}

/* 喇叭按钮通用样式 */
.audio-btn  {

  font-size: 20px;
  padding: 8px 12px;
  border-radius: 50%;
  margin-left: 8px;
  vertical-align: middle;
}

.audio-btn-table  {

  font-size: 13px;
  flex-shrink: 0;
  margin-left: 0;
}

.question-actions  {

  margin-top: 40px;
  text-align: center;
  flex-shrink: 0;
}

.question-actions .el-button  {

  font-size: 28px;
  padding: 25px 80px;
}

.review-result  {

  padding: 24px;
  display: flex;
  flex-direction: column;
  height: 100%;
  max-height: 75vh;
  overflow: hidden;
}

.result-header  {

  display: flex;
  gap: 20px;
  margin-bottom: 16px;
  flex-shrink: 0;
}

.accuracy-display  {

  flex: 1;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  border-radius: 20px;
  padding: 32px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
}

.accuracy-big  {

  font-size: 80px;
  font-weight: bold;
  color: #fff;
  line-height: 1;
}

.accuracy-label  {

  font-size: 20px;
  color: rgba(255,255,255,0.85);
  margin-top: 8px;
}

.stats-panel  {

  flex: 1.1;
  background: linear-gradient(145deg, #f5f7fa 0%, #e8ecf1 100%);
  border-radius: 20px;
  padding: 20px 24px;
  display: grid;
  grid-template-columns: 1fr 1fr;
  grid-template-rows: 1fr 1fr;
  gap: 14px;
}

.stat-item  {

  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  background: #fff;
  border-radius: 12px;
  padding: 12px;
}

.stat-item.correct .stat-value  {
   color: #67c23a;
   }
.stat-item.error .stat-value  {
   color: #f56c6c;
   }

.stat-value  {

  font-size: 32px;
  font-weight: bold;
  color: var(--accent-blue);
  line-height: 1;
}

.stat-label  {

  font-size: 13px;
  color: var(--text-muted);
  margin-top: 4px;
}

.error-word-list  {

  flex: 1;
  overflow: hidden;
  display: flex;
  flex-direction: column;
}

.error-word-list .error-words-scroll  {

  flex: 1;
  overflow-y: auto;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(240px, 1fr));
  gap: 10px;
  padding: 4px;
}

.error-word-item  {

  display: flex;
  background: #fff;
  border-radius: 10px;
  overflow: hidden;
  box-shadow: 0 1px 4px rgba(0,0,0,0.08);
}

.correct-side  {

  flex: 1;
  background: linear-gradient(135deg, #67c23a 0%, #5daf34 100%);
  padding: 12px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.correct-en  {

  font-size: 18px;
  font-weight: bold;
  color: #fff;
}

.correct-cn  {

  font-size: 13px;
  color: rgba(255,255,255,0.9);
  margin-top: 2px;
}

.wrong-side  {

  width: 100px;
  background: #fef0f0;
  padding: 12px 8px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  border-left: 2px solid #f56c6c;
}

.wrong-tag  {

  font-size: 10px;
  color: #f56c6c;
  font-weight: bold;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}

.wrong-answer  {

  font-size: 14px;
  font-weight: bold;
  color: #f56c6c;
  text-align: center;
  word-break: break-all;
  margin-top: 4px;
}

.finish-btn  {

  margin-top: 12px;
  flex-shrink: 0;
  height: 44px;
  font-size: 16px;
}





.words-preview  {

  margin-top: 10px;
  border: 1px solid #ebeef5;
  border-radius: 4px;
  padding: 10px;
  background-color: #fafafa;
}

.preview-summary  {

  margin-top: 10px;
  text-align: right;
  color: var(--text-muted);
  font-size: 14px;
}

/* 记忆曲线样式 */
.memory-curve  {

  padding: 20px;
}
.phase-bar  {

  margin-bottom: 20px;
}
.phase-track  {

  position: relative;
  height: 40px;
  background: #f0f0f0;
  border-radius: 20px;
}
.phase-dot  {

  position: absolute;
  top: 50%;
  transform: translate(-50%, -50%);
  padding: 4px 8px;
  background: #fff;
  border-radius: 4px;
  font-size: 12px;
  border: 2px solid #ddd;
}
.phase-dot.active  {

  background: var(--accent-blue);
  color: #fff;
  border-color: var(--accent-blue);
}
.next-review  {

  margin-bottom: 20px;
  font-size: 16px;
  color: #666;
}
.review-history  {

  border-top: 1px solid #eee;
  padding-top: 15px;
}
.history-title  {

  font-weight: bold;
  margin-bottom: 10px;
}
.history-item  {

  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 0;
  font-size: 14px;
}
.history-date  {

  min-width: 100px;
}
.history-correct  {

  color: #67c23a;
}
.history-wrong  {

  color: #f56c6c;
}

/* 禁用卡片的hover效果 */
.words :deep(.el-card)  {

  transition: none;
}
.words :deep(.el-card:hover)  {

  transform: none;
  box-shadow: var(--shadow-sm) !important;
}
.words {
  max-width:none}
.word-english {
  color:var(--accent-blue)}
.card-header>div {
  display:flex;
  flex-wrap:wrap;
  gap:6px}
.card-header :deep(.el-button+.el-button) {
  margin-left:0}
.review-config {
  padding:24px;
  font-size:16px}
.review-question {
  padding:24px}
.question-header {
  gap:24px;
  margin-bottom:20px}
.progress {
  font-size:25px}
.timer {
  font-size:23px}
.result-display {
  padding:18px 25px;
  margin-bottom:20px}
.result-status {
  font-size:24px}
.result-answer-large {
  font-size:28px}
@media(max-width:768px) {
  .review-config,.review-question {
  padding:14px}
.review-question {
  height:auto;
  min-height:60vh}
.question-header {
  gap:18px}
.question-content {
  min-width:0}
}

.phrase-tag {
  margin-left: 6px;
  flex-shrink: 0;
}

.focus-status-line {
  margin-bottom: 10px;
  color: var(--text-secondary);
}

.type-stats {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  margin-bottom: 12px;
}

.type-stat {
  display: flex;
  align-items: baseline;
  flex-wrap: wrap;
  gap: 8px;
  padding: 8px 14px;
  border-radius: var(--radius-md);
  background: var(--bg-tertiary);
  border: 1px solid var(--border-light);
}

.type-stat-name {
  font-weight: var(--font-weight-semibold);
  color: var(--text-primary);
}

.type-stat-num {
  color: var(--accent-blue);
  font-weight: var(--font-weight-bold);
}

.type-stat-acc {
  color: var(--text-secondary);
  font-size: var(--font-small);
}
</style>

<style>
/* 手机上限制弹窗宽度，避免横向溢出 */
.detail-dialog,
.print-dialog {
  max-width: 94vw;
}
</style>

<style>
.toast-large.el-message  {

  font-size: 24px !important;
  padding: 20px 30px !important;
  min-width: 300px !important;
}
.toast-large.el-message .el-message__content  {

  font-size: 24px !important;
}
</style>
