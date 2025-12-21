/**
 * @file main.cpp
 * @brief Event system implementation with observer pattern.
 *
 * Provides a type-safe event emitter with support for
 * synchronous and asynchronous event handling.
 */

#include <functional>
#include <unordered_map>
#include <vector>
#include <memory>
#include <mutex>
#include <future>
#include <iostream>
#include <string>
#include <typeindex>
#include <any>

namespace events {

/**
 * @brief Base class for all events.
 *
 * Events can be stopped from propagating and can carry
 * metadata about when they were created.
 */
class Event {
public:
    Event() : propagation_stopped_(false) {}
    virtual ~Event() = default;

    /**
     * @brief Get the event type name.
     * @return String identifier for the event type.
     */
    virtual std::string type() const = 0;

    /**
     * @brief Stop the event from propagating to other listeners.
     */
    void stopPropagation() { propagation_stopped_ = true; }

    /**
     * @brief Check if propagation was stopped.
     * @return True if stopPropagation was called.
     */
    bool isPropagationStopped() const { return propagation_stopped_; }

private:
    bool propagation_stopped_;
};

/**
 * @brief Listener identifier for unsubscription.
 */
using ListenerId = size_t;

/**
 * @brief Generic event handler function type.
 */
template<typename E>
using Handler = std::function<void(const E&)>;

/**
 * @brief Type-erased handler storage.
 */
struct HandlerEntry {
    std::any handler;
    bool once;
    ListenerId id;
};

/**
 * @brief Thread-safe event emitter with type-safe handlers.
 *
 * Supports multiple listeners per event type, one-time listeners,
 * and async event emission.
 *
 * @code
 * EventEmitter emitter;
 *
 * emitter.on<UserCreatedEvent>([](const UserCreatedEvent& e) {
 *     std::cout << "User created: " << e.username << std::endl;
 * });
 *
 * emitter.emit(UserCreatedEvent{"john_doe"});
 * @endcode
 */
class EventEmitter {
public:
    EventEmitter() : next_id_(0) {}

    /**
     * @brief Subscribe to an event type.
     *
     * @tparam E The event type to listen for.
     * @param handler Function to call when event is emitted.
     * @return ListenerId for later unsubscription.
     */
    template<typename E>
    ListenerId on(Handler<E> handler) {
        return subscribe<E>(std::move(handler), false);
    }

    /**
     * @brief Subscribe to an event type for a single emission.
     *
     * The handler will be automatically removed after being called once.
     *
     * @tparam E The event type to listen for.
     * @param handler Function to call when event is emitted.
     * @return ListenerId for manual unsubscription if needed.
     */
    template<typename E>
    ListenerId once(Handler<E> handler) {
        return subscribe<E>(std::move(handler), true);
    }

    /**
     * @brief Unsubscribe a specific listener.
     *
     * @tparam E The event type the listener was registered for.
     * @param id The ListenerId returned from on() or once().
     * @return True if the listener was found and removed.
     */
    template<typename E>
    bool off(ListenerId id) {
        std::lock_guard<std::mutex> lock(mutex_);
        auto type = std::type_index(typeid(E));

        auto it = handlers_.find(type);
        if (it == handlers_.end()) return false;

        auto& vec = it->second;
        for (auto iter = vec.begin(); iter != vec.end(); ++iter) {
            if (iter->id == id) {
                vec.erase(iter);
                return true;
            }
        }
        return false;
    }

    /**
     * @brief Emit an event to all registered listeners.
     *
     * Listeners are called in the order they were registered.
     * If a listener calls stopPropagation(), subsequent listeners
     * will not be called.
     *
     * @tparam E The event type.
     * @param event The event to emit.
     * @return Number of listeners that received the event.
     */
    template<typename E>
    size_t emit(const E& event) {
        std::vector<HandlerEntry> to_call;
        std::vector<ListenerId> to_remove;

        {
            std::lock_guard<std::mutex> lock(mutex_);
            auto type = std::type_index(typeid(E));

            auto it = handlers_.find(type);
            if (it == handlers_.end()) return 0;

            to_call = it->second;
        }

        size_t called = 0;
        for (auto& entry : to_call) {
            if (event.isPropagationStopped()) break;

            try {
                auto& handler = std::any_cast<Handler<E>&>(entry.handler);
                handler(event);
                called++;

                if (entry.once) {
                    to_remove.push_back(entry.id);
                }
            } catch (const std::bad_any_cast&) {
                // Handler type mismatch - shouldn't happen
            }
        }

        // Clean up one-time listeners
        for (auto id : to_remove) {
            off<E>(id);
        }

        return called;
    }

    /**
     * @brief Emit an event asynchronously.
     *
     * @tparam E The event type.
     * @param event The event to emit.
     * @return Future resolving to number of listeners called.
     */
    template<typename E>
    std::future<size_t> emitAsync(const E& event) {
        return std::async(std::launch::async, [this, event]() {
            return emit(event);
        });
    }

    /**
     * @brief Get the number of listeners for an event type.
     *
     * @tparam E The event type.
     * @return Number of registered listeners.
     */
    template<typename E>
    size_t listenerCount() const {
        std::lock_guard<std::mutex> lock(mutex_);
        auto type = std::type_index(typeid(E));

        auto it = handlers_.find(type);
        if (it == handlers_.end()) return 0;
        return it->second.size();
    }

    /**
     * @brief Remove all listeners for an event type.
     *
     * @tparam E The event type.
     */
    template<typename E>
    void removeAllListeners() {
        std::lock_guard<std::mutex> lock(mutex_);
        auto type = std::type_index(typeid(E));
        handlers_.erase(type);
    }

private:
    template<typename E>
    ListenerId subscribe(Handler<E> handler, bool once) {
        std::lock_guard<std::mutex> lock(mutex_);
        auto type = std::type_index(typeid(E));

        ListenerId id = next_id_++;
        handlers_[type].push_back({std::any(std::move(handler)), once, id});
        return id;
    }

    mutable std::mutex mutex_;
    std::unordered_map<std::type_index, std::vector<HandlerEntry>> handlers_;
    ListenerId next_id_;
};

// Example event types
struct UserCreatedEvent : public Event {
    std::string username;

    explicit UserCreatedEvent(std::string name) : username(std::move(name)) {}
    std::string type() const override { return "UserCreated"; }
};

struct MessageReceivedEvent : public Event {
    std::string sender;
    std::string content;

    MessageReceivedEvent(std::string s, std::string c)
        : sender(std::move(s)), content(std::move(c)) {}
    std::string type() const override { return "MessageReceived"; }
};

} // namespace events
