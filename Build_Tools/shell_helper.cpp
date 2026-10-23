// Explorer hands the complete selection to this COM command handler.
// No file-count or command-line-length limit is imposed by the application.
#include <windows.h>
#include <shlobj.h>
#include <shobjidl.h>
#include <shellapi.h>
#include <wrl/client.h>
#include <atomic>
#include <filesystem>
#include <string>
#include <vector>

using Microsoft::WRL::ComPtr;
static std::atomic<long> objects{0}, locks{0};
static HMODULE module = nullptr;
struct Config {
    std::wstring player, requestDir;
    std::vector<std::wstring> prefix;
};
static std::wstring registryString(HKEY root, const std::wstring& key, const wchar_t* name) {
    DWORD bytes = 0;
    if (RegGetValueW(root, key.c_str(), name, RRF_RT_REG_SZ, nullptr, nullptr, &bytes) != ERROR_SUCCESS) return {};
    std::wstring value(bytes / sizeof(wchar_t), L'\0');
    if (RegGetValueW(root, key.c_str(), name, RRF_RT_REG_SZ, nullptr, value.data(), &bytes) != ERROR_SUCCESS) return {};
    while (!value.empty() && value.back() == L'\0') value.pop_back();
    return value;
}
static Config configuration(REFCLSID clsid) {
    wchar_t id[40]{};
    StringFromGUID2(clsid, id, 40);
    std::wstring key = std::wstring(L"Software\\Classes\\CLSID\\") + id;
    Config config;
    config.player = registryString(HKEY_CURRENT_USER, key, L"PlayerExecutable");
    if (config.player.empty()) config.player = registryString(HKEY_LOCAL_MACHINE, key, L"PlayerExecutable");
    if (config.player.empty()) {
        wchar_t path[32768]{};
        GetModuleFileNameW(module, path, 32768);
        config.player = (std::filesystem::path(path).parent_path() / L"AudioPlayer.exe").wstring();
    }
    config.requestDir = registryString(HKEY_CURRENT_USER, key, L"RequestDirectory");
    if (config.requestDir.empty()) {
        PWSTR local = nullptr;
        if (SUCCEEDED(SHGetKnownFolderPath(FOLDERID_LocalAppData, 0, nullptr, &local))) {
            config.requestDir = std::wstring(local) + L"\\AudioPlayer\\shell-requests";
            CoTaskMemFree(local);
        }
    }
    DWORD bytes = 0;
    if (RegGetValueW(HKEY_CURRENT_USER, key.c_str(), L"PrefixArguments", RRF_RT_REG_MULTI_SZ,
                    nullptr, nullptr, &bytes) == ERROR_SUCCESS) {
        std::vector<wchar_t> data(bytes / sizeof(wchar_t) + 1, L'\0');
        if (RegGetValueW(HKEY_CURRENT_USER, key.c_str(), L"PrefixArguments", RRF_RT_REG_MULTI_SZ,
                        nullptr, data.data(), &bytes) == ERROR_SUCCESS) {
            for (const wchar_t* p = data.data(); *p; p += wcslen(p) + 1) config.prefix.emplace_back(p);
        }
    }
    return config;
}

static std::wstring quote(const std::wstring& value) {
    std::wstring result = L"\"";
    size_t slashes = 0;
    for (wchar_t c : value) {
        if (c == L'\\') { ++slashes; continue; }
        result.append(slashes * (c == L'\"' ? 2 : 1), L'\\');
        slashes = 0;
        if (c == L'\"') result += L'\\';
        result += c;
    }
    result.append(slashes * 2, L'\\');
    return result + L'\"';
}

static bool writeBytes(HANDLE file, const std::string& bytes) {
    DWORD written = 0;
    return WriteFile(file, bytes.data(), static_cast<DWORD>(bytes.size()), &written, nullptr)
        && written == bytes.size();
}

static std::string jsonPath(const wchar_t* path) {
    int length = WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, path, -1, nullptr, 0, nullptr, nullptr);
    if (!length) return {};
    std::string utf8(length, '\0');
    if (!WideCharToMultiByte(CP_UTF8, WC_ERR_INVALID_CHARS, path, -1, utf8.data(), length, nullptr, nullptr)) return {};
    utf8.pop_back();
    std::string result = "\"";
    const char hex[] = "0123456789abcdef";
    for (unsigned char c : utf8) {
        if (c == '\\' || c == '"') { result += '\\'; result += c; }
        else if (c < 32) { result += "\\u00"; result += hex[c >> 4]; result += hex[c & 15]; }
        else result += c;
    }
    return result + '"';
}

static HRESULT openSelection(IShellItemArray* selection, const Config& config) {
    if (!selection) return E_INVALIDARG;
    DWORD count = 0;
    HRESULT hr = selection->GetCount(&count);
    if (FAILED(hr) || !count) return hr;
    std::error_code error;
    std::filesystem::create_directories(config.requestDir, error);
    if (error) return HRESULT_FROM_WIN32(error.value());
    GUID id{};
    if (FAILED(hr = CoCreateGuid(&id))) return hr;
    wchar_t name[40]{};
    StringFromGUID2(id, name, 40);
    std::wstring path = config.requestDir + L"\\" + name + L".json";
    HANDLE file = CreateFileW(path.c_str(), GENERIC_WRITE, 0, nullptr, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, nullptr);
    if (file == INVALID_HANDLE_VALUE) return HRESULT_FROM_WIN32(GetLastError());
    bool ok = writeBytes(file, "[");
    DWORD accepted = 0;
    for (DWORD index = 0; ok && index < count; ++index) {
        ComPtr<IShellItem> item;
        PWSTR filename = nullptr;
        if (FAILED(hr = selection->GetItemAt(index, &item))) { ok = false; break; }
        hr = item->GetDisplayName(SIGDN_FILESYSPATH, &filename);
        if (FAILED(hr)) { ok = false; break; }
        auto encoded = jsonPath(filename);
        CoTaskMemFree(filename);
        if (encoded.empty()) { hr = E_INVALIDARG; ok = false; break; }
        ok = (!accepted || writeBytes(file, ",")) && writeBytes(file, encoded);
        ++accepted;
    }
    ok = ok && writeBytes(file, "]") && FlushFileBuffers(file);
    DWORD writeError = GetLastError();
    CloseHandle(file);
    if (!ok) {
        DeleteFileW(path.c_str());
        return FAILED(hr) ? hr : HRESULT_FROM_WIN32(writeError ? writeError : ERROR_WRITE_FAULT);
    }
    std::wstring command = quote(config.player);
    for (const auto& arg : config.prefix) command += L" " + quote(arg);
    command += L" --open-list " + quote(path);
    STARTUPINFOW startup{sizeof(startup)};
    PROCESS_INFORMATION process{};
    if (!CreateProcessW(config.player.c_str(), command.data(), nullptr, nullptr, FALSE, 0, nullptr,
                        nullptr, &startup, &process)) {
        DWORD createError = GetLastError();
        DeleteFileW(path.c_str());
        return HRESULT_FROM_WIN32(createError);
    }
    CloseHandle(process.hThread);
    CloseHandle(process.hProcess);
    return S_OK;
}

class SelectionCommand final : public IExecuteCommand, public IObjectWithSelection {
    std::atomic<ULONG> references{1};
    ComPtr<IShellItemArray> selection;
    Config config;
public:
    explicit SelectionCommand(const Config& value) : config(value) { ++objects; }
    ~SelectionCommand() { --objects; }
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** result) override {
        if (!result) return E_POINTER;
        *result = nullptr;
        if (iid == IID_IUnknown || iid == __uuidof(IExecuteCommand))
            *result = static_cast<IExecuteCommand*>(this);
        else if (iid == __uuidof(IObjectWithSelection))
            *result = static_cast<IObjectWithSelection*>(this);
        else return E_NOINTERFACE;
        AddRef();
        return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++references; }
    ULONG STDMETHODCALLTYPE Release() override {
        ULONG remaining = --references;
        if (!remaining) delete this;
        return remaining;
    }
    HRESULT STDMETHODCALLTYPE SetSelection(IShellItemArray* value) override { selection = value; return S_OK; }
    HRESULT STDMETHODCALLTYPE GetSelection(REFIID iid, void** result) override {
        return selection ? selection->QueryInterface(iid, result) : E_UNEXPECTED;
    }
    HRESULT STDMETHODCALLTYPE SetKeyState(DWORD) override { return S_OK; }
    HRESULT STDMETHODCALLTYPE SetParameters(LPCWSTR) override { return S_OK; }
    HRESULT STDMETHODCALLTYPE SetPosition(POINT) override { return S_OK; }
    HRESULT STDMETHODCALLTYPE SetShowWindow(int) override { return S_OK; }
    HRESULT STDMETHODCALLTYPE SetNoShowUI(BOOL) override { return S_OK; }
    HRESULT STDMETHODCALLTYPE SetDirectory(LPCWSTR) override { return S_OK; }
    HRESULT STDMETHODCALLTYPE Execute() override {
        try { return openSelection(selection.Get(), config); }
        catch (...) { return E_OUTOFMEMORY; }
    }
};

class Factory final : public IClassFactory {
    std::atomic<ULONG> references{1};
    Config config;
public:
    explicit Factory(REFCLSID clsid) : config(configuration(clsid)) { ++objects; }
    ~Factory() { --objects; }
    HRESULT STDMETHODCALLTYPE QueryInterface(REFIID iid, void** result) override {
        if (!result) return E_POINTER;
        *result = nullptr;
        if (iid != IID_IUnknown && iid != IID_IClassFactory) return E_NOINTERFACE;
        *result = static_cast<IClassFactory*>(this);
        AddRef();
        return S_OK;
    }
    ULONG STDMETHODCALLTYPE AddRef() override { return ++references; }
    ULONG STDMETHODCALLTYPE Release() override {
        ULONG remaining = --references;
        if (!remaining) delete this;
        return remaining;
    }
    HRESULT STDMETHODCALLTYPE CreateInstance(IUnknown* outer, REFIID iid, void** result) override {
        if (outer) return CLASS_E_NOAGGREGATION;
        try {
            auto* command = new(std::nothrow) SelectionCommand(config);
            if (!command) return E_OUTOFMEMORY;
            HRESULT hr = command->QueryInterface(iid, result);
            command->Release();
            return hr;
        } catch (...) { return E_OUTOFMEMORY; }
    }
    HRESULT STDMETHODCALLTYPE LockServer(BOOL lock) override {
        if (lock) ++locks; else --locks;
        return S_OK;
    }
};

STDAPI DllGetClassObject(REFCLSID clsid, REFIID iid, void** result) {
    try {
        auto* factory = new(std::nothrow) Factory(clsid);
        if (!factory) return E_OUTOFMEMORY;
        HRESULT hr = factory->QueryInterface(iid, result);
        factory->Release();
        return hr;
    } catch (...) { return E_OUTOFMEMORY; }
}
STDAPI DllCanUnloadNow() {
    return !objects && !locks ? S_OK : S_FALSE;
}
BOOL WINAPI DllMain(HINSTANCE instance, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_ATTACH) module = instance;
    return TRUE;
}
