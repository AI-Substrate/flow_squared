# Embedding Reprocessing Investigation Report

Generated: 2026-01-14T03:03:53.062494

## Summary

- Nodes after scan 1: 4414
- Nodes after scan 2: 4414
- Nodes needing enrichment after scan 2: 183

## Content Hash Changes

### type:tests/fixtures/samples/javascript/app.ts:Application.@106
- **end_line**:
  - before: `226`
  - after: `106`
- **content**:
  - before: `<3223 chars, hash=b9e2346001dc8910>`
  - after: `'extends EventEmitter'`
- **content_hash**:
  - before: `'b9e2346001dc8910f9243c963bb51a725c2aaa3817f7c317dd826757985393d5'`
  - after: `'6f48478baf08015b4579e5396811b14ff0555f3a42b113477c2b6b272d42fba0'`
- **smart_content**:
  - before: `<554 chars, hash=1e7d318292842e88>`
  - after: `"[Empty content - no summary generated for type '@106']"`
- **smart_content_hash**:
  - before: `'b9e2346001dc8910f9243c963bb51a725c2aaa3817f7c317dd826757985393d5'`
  - after: `'6f48478baf08015b4579e5396811b14ff0555f3a42b113477c2b6b272d42fba0'`
- **embedding**:
  - before: `<1 vectors>`
  - after: `<1 vectors>`
- **embedding_hash**:
  - before: `'b9e2346001dc8910f9243c963bb51a725c2aaa3817f7c317dd826757985393d5'`
  - after: `'6f48478baf08015b4579e5396811b14ff0555f3a42b113477c2b6b272d42fba0'`
- **smart_content_embedding**:
  - before: `<1 vectors>`
  - after: `None`

### type:tests/fixtures/ast_samples/typescript/class_generics.ts:GenericRepository.@1
- **end_line**:
  - before: `12`
  - after: `1`
- **content**:
  - before: `<261 chars, hash=d92c67a810584763>`
  - after: `'implements Repository<T>'`
- **content_hash**:
  - before: `'d92c67a810584763512f535eaa8cbec46499ba09fc23e64ed260a633238ab78c'`
  - after: `'d34b8c31d15f38c3b897d498bbcbf05649eaa4367c0f9ecce6c41efd6f044e6b'`
- **smart_content**:
  - before: `<376 chars, hash=f875da2e5c517269>`
  - after: `"[Empty content - no summary generated for type '@1']"`
- **smart_content_hash**:
  - before: `'d92c67a810584763512f535eaa8cbec46499ba09fc23e64ed260a633238ab78c'`
  - after: `'d34b8c31d15f38c3b897d498bbcbf05649eaa4367c0f9ecce6c41efd6f044e6b'`
- **embedding**:
  - before: `<1 vectors>`
  - after: `<1 vectors>`
- **embedding_hash**:
  - before: `'d92c67a810584763512f535eaa8cbec46499ba09fc23e64ed260a633238ab78c'`
  - after: `'d34b8c31d15f38c3b897d498bbcbf05649eaa4367c0f9ecce6c41efd6f044e6b'`
- **smart_content_embedding**:
  - before: `<1 vectors>`
  - after: `None`

### callable:tests/fixtures/samples/c/main.cpp:Event.@31.@31
- **content**:
  - before: `'= default;'`
  - after: `'~Event()'`
- **content_hash**:
  - before: `'8a75ef90a37cbf74ff5fb668774adae3eb9ec1105af98a8c7176cef72f07f3cd'`
  - after: `'ae271b4a746223dd5aff7f516cefb0c834cbdb8c50b221d673f338a71ca4b173'`
- **smart_content_hash**:
  - before: `'8a75ef90a37cbf74ff5fb668774adae3eb9ec1105af98a8c7176cef72f07f3cd'`
  - after: `'ae271b4a746223dd5aff7f516cefb0c834cbdb8c50b221d673f338a71ca4b173'`
- **embedding**:
  - before: `<1 vectors>`
  - after: `<1 vectors>`
- **embedding_hash**:
  - before: `'8a75ef90a37cbf74ff5fb668774adae3eb9ec1105af98a8c7176cef72f07f3cd'`
  - after: `'ae271b4a746223dd5aff7f516cefb0c834cbdb8c50b221d673f338a71ca4b173'`


## Persistent Reprocessing Candidates

### file:src/fs2/core/services/embedding/__init__.py
- has_smart_content_but_no_smart_content_embedding

### file:src/fs2/cli/__init__.py
- has_smart_content_but_no_smart_content_embedding

### file:tests/unit/repos/__init__.py
- has_smart_content_but_no_smart_content_embedding

### file:tests/unit/services/stages/__init__.py
- has_smart_content_but_no_smart_content_embedding

### callable:tests/unit/services/test_scan_pipeline.py:TestScanPipelineCustomStages.test_given_custom_stages_when_constructing_then_uses_custom_stages.CustomStage.name
- has_smart_content_but_no_smart_content_embedding

### callable:tests/unit/services/test_scan_pipeline.py:TestScanPipelinePriorNodesLoading.test_given_existing_graph_when_running_then_prior_nodes_populated.ContextCapturingStage.name
- has_smart_content_but_no_smart_content_embedding

### callable:tests/unit/services/test_scan_pipeline.py:TestScanPipelinePriorNodesLoading.test_given_no_graph_exists_when_running_then_prior_nodes_is_none.ContextCapturingStage.name
- has_smart_content_but_no_smart_content_embedding

### callable:tests/unit/services/test_scan_pipeline.py:TestScanPipelinePriorNodesLoading.test_given_corrupted_graph_when_running_then_prior_nodes_is_none_and_logs_warning.ContextCapturingStage.name
- has_smart_content_but_no_smart_content_embedding

### callable:tests/unit/services/test_scan_pipeline.py:TestScanPipelinePriorNodesLoading.test_given_existing_graph_when_running_then_prior_nodes_is_dict_by_node_id.ContextCapturingStage.name
- has_smart_content_but_no_smart_content_embedding

### callable:tests/unit/services/test_pipeline_stage.py:TestPipelineStageRuntimeCheckable.test_given_non_conforming_class_when_isinstance_checked_then_returns_false.NonConformingClass.do_something
- has_smart_content_but_no_smart_content_embedding

### file:tests/integration/__init__.py
- has_smart_content_but_no_smart_content_embedding

### file:tests/__init__.py
- has_smart_content_but_no_smart_content_embedding

### file:tests/mcp_tests/__init__.py
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/go/server.go:@41.@43
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/go/server.go:HandlerFunc
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/go/server.go:NewServer.@72.@73
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/go/server.go:wrapHandler.@100.@103
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/go/server.go:wrapHandler.@100.@107.@108
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/go/server.go:StartWithGracefulShutdown.@148.@151.@152
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/go/server.go:Shutdown.@171.@173
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/go/server.go:JSON.@212
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/gdscript/player.gd:Player
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/cuda/vector_add.cu:@1.vectorAdd
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/cuda/vector_add.cu:@8.launchKernel
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:EvictionPolicy.@13.LRU
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:EvictionPolicy.@13.LFU
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:EvictionPolicy.@13.FIFO
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:@52.Clone
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/rust/lib.rs:@52.is_expired.@63
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:CacheError.@75.NotFound
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:CacheError.@75.Expired
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:CacheError.@75.Full
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:Cacheable.Clone
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:Cacheable@87.Clone
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:Cache.Eq
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:Cache.Cacheable
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:@99.Eq
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:@99.Cacheable
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/rust/lib.rs:@99.with_defaults.@113
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:@99.get.None.Some
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:@99.clear.@157.Ok
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/rust/lib.rs:@99.clear.@157.@158
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/rust/lib.rs:@99.is_empty.@169
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:@99.evict_one.@186.Some
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/rust/lib.rs:@99.evict_one.@186.@202
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:Clone.Eq
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/rust/lib.rs:Clone.Cacheable
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/java/UserService.java:UserService.@18.UserException.RuntimeException
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/java/UserService.java:UserRepository.@285.findById
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/java/UserService.java:UserRepository.@285.save
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/java/UserService.java:UserRepository.@285.findAll
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/java/UserService.java:EmailService.@292.sendWelcomeEmail
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/java/UserService.java:CacheManager.@296.get
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/java/UserService.java:CacheManager.@296.put
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/java/UserService.java:CacheManager.@296.invalidate
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/javascript/app.ts:LogLevel.@12.DEBUG
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/javascript/app.ts:LogLevel.@12.INFO
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/javascript/app.ts:LogLevel.@12.WARN
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/javascript/app.ts:LogLevel.@12.ERROR
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/app.ts:AppEvents.@95.@96
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/app.ts:AppEvents.@95.@97
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/app.ts:AppEvents.@95.@98
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/app.ts:AppEvents.@95.@99
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/app.ts:AppEvents.@95.@100
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/javascript/app.ts:Application.@106
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/javascript/component.tsx:ButtonSize
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/component.tsx:ThemeContextValue.@49.@51
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/component.tsx:ThemeProvider.@108
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/component.tsx:ThemeProvider.@108.@109
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/component.tsx:useAsync.@221
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/component.tsx:useAsync.@234.@258
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/component.tsx:useDebounce.@272.@273
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/component.tsx:useDebounce.@272.@277
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/component.tsx:usePrevious.@289
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/utils.js:deepClone.@77
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/javascript/utils.js:retryWithBackoff.@166
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/algorithm.c:@20
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/c/algorithm.c:@45.@45
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/algorithm.c:@45.swap
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/c/algorithm.c:@138.@138
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/c/algorithm.c:@224.@224
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/algorithm.c:@273.compare_int_asc
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/algorithm.c:@282.compare_int_desc
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:Event.@30
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:Event.@30.Event
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:Event.@31
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:Event.@31.@31
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/c/main.cpp:Event.@31.@31.Event
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:Event.@37
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:Event.@42.@42
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:Event.@48.@48
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:@63
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@92
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@92.EventEmitter
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.ListenerId.on
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.ListenerId.subscribe
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.ListenerId@116.once
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.ListenerId@116.subscribe
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@128.off
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@128.lock
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@157.emit
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@157.lock
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@157.any_cast
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@157.off
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@204.emitAsync
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@217.listenerCount
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@217.lock
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@232.removeAllListeners
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.@232.lock
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.ListenerId@240.subscribe
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:EventEmitter.ListenerId@240.lock
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/c/main.cpp:UserCreatedEvent.Event
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:UserCreatedEvent.@258.@258
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:UserCreatedEvent.@258.UserCreatedEvent
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:UserCreatedEvent.@259.@259
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/c/main.cpp:MessageReceivedEvent.Event
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/c/main.cpp:MessageReceivedEvent.@268.@268
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.initialize.@37
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.migrate_up.@54.@56
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.rollback.@67
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.rollback.@72.@74
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.status.@85.@87
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.status.@85.@88
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.all_migrations.@101
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.all_migrations.@101.@101
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.pending_migrations.@105
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.applied_migrations.@109
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.migration_applied?.migration
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.apply_migration.migration
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/ruby/tasks.rb:MigrationRunner.revert_migration.migration
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/ruby/tasks.rb:Seeder.initialize.@130
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/ruby/tasks.rb:Seeder.seed.@139
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/ruby/tasks.rb:Seeder.seed.@139.@139
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/samples/ruby/tasks.rb:Seeder.create_unless_exists.table
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/ruby/tasks.rb:@162.@176.@177
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/ruby/tasks.rb:@162.@189.@196.@197
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/samples/ruby/tasks.rb:@162.@203.@204
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/go/interfaces.go:@7
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/go/interfaces.go:@7.GetID
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/go/interfaces.go:@11.Find
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/go/interfaces.go:@11.Save
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/go/interfaces.go:@16
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/go/interfaces.go:GetID
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/ast_samples/go/interfaces.go:GetID.@21
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/go/interfaces.go:@25
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/ast_samples/go/interfaces.go:Find.@29.@30
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/go/structs_methods.go:@3
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/ast_samples/go/structs_methods.go:NewCalculator.@7
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/ast_samples/go/structs_methods.go:Add.@11
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/ast_samples/go/structs_methods.go:Value.@16
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/gdscript/player.gd:Player
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/python/standalone_functions.py:fetch_data
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/python/standalone_functions.py:_private_helper
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/python/decorators_async.py:Service.status
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/python/decorators_async.py:Service.create
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/python/nested_classes.py:Outer.Inner.inner_method
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/python/nested_classes.py:Outer.create_closure.closure_func
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/python/nested_classes.py:Outer.processor
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/cuda/vector_add.cu:@1.vectorAdd
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/cuda/vector_add.cu:@8.launchKernel
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/typescript/react_component.tsx:Props.@1
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/typescript/react_component.tsx:Props.@1.@3
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/typescript/standalone.js:processData.item
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/typescript/standalone.js:@5
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/typescript/interfaces_types.ts:Status
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/typescript/interfaces_types.ts:Repository.@9.find
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/typescript/interfaces_types.ts:Repository.@9.save
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/typescript/class_generics.ts:GenericRepository.@1
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/typescript/class_generics.ts:GenericRepository.@1.@1
- has_smart_content_but_no_smart_content_embedding

### file:tests/fixtures/ast_samples/edge_cases/empty.py
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/edge_cases/unicode_names.py:calculate_total
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/edge_cases/unicode_names.py:DataProcessor.process
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/rust/structs_impl.rs:Calculator
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/ast_samples/rust/structs_impl.rs:Calculator@5.new.@6
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/rust/structs_impl.rs:Calculator@5.new.@6.Self
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/rust/structs_impl.rs:Default.default
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/ast_samples/rust/structs_impl.rs:Default.default.@17
- has_smart_content_but_no_smart_content_embedding

### callable:tests/fixtures/ast_samples/rust/traits_generics.rs:Repository.find
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/rust/traits_generics.rs:InMemoryRepo
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/ast_samples/rust/traits_generics.rs:@10.find.@11
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/ast_samples/csharp/namespace_class.cs:UserService.UserService.@8
- has_smart_content_but_no_smart_content_embedding

### type:tests/fixtures/ast_samples/csharp/async_linq.cs:DataProcessor.ProcessAsync.@8.@9
- has_smart_content_but_no_smart_content_embedding

### block:tests/fixtures/ast_samples/csharp/properties_methods.cs:Person.UpdateAge.@12
- has_smart_content_but_no_smart_content_embedding

