1. For the first issue:

```php
// AuditLoggingTrait.php

namespace App\Traits;

use Illuminate\Database\Eloquent\Model;

trait AuditLoggingTrait
{
    public static function boot()
    {
        static::saving(function ($model) {
            $model->created_by = $model->get_user();
            $model->updated_by = $model->get_user();
        });

        static::created(function ($model) {
            $model->created_by = $model->get_user();
            $model->save();
        });

        static::deleted(function ($model) {
            $model->deleted_by = $model->get_user();
            $model->save();
        });
    }

    public function get_user()
    {
        return auth()->id();
    }
}
```

2. For the second issue:

```php
// APIKeyAuth.php

namespace App\Http\Controllers\API;

use App\Models\User;
use Illuminate\Support\Facades\Auth;

class APIKeyAuth
{
    public function __construct()
    {
        $this->current_key = $this->get_key();
    }

    public function get_key()
    {
        return User::where('api_key', $this->current_key)->first();
    }

    public function is_key_expired()
    {
        $user = $this->get_key();
        return $user ? $user->api_key : null;
    }

    public function get_current_key()
    {
        return $this->current_key;
    }

    public function set_current_key($key)
    {
        $this->current_key = $key;
    }

    public function get_state()
    {
        return [
            'current_key' => $this->current_key,
        ];
    }
}
```

3. For the third issue:

```php
// ApiController.php

namespace App\Http\Controllers\API;

use App\Models\User;
use Illuminate\Support\Facades\Auth;
use Illuminate\Support\Facades\Hash;

class ApiController extends \ApiController
{
    public function login()
    {
        $email = request('email');
        $password = request('password');
        if (auth()->attempt(['email' => $email, 'password' => $password])) {
            $token = auth()->user()->createToken('api_token')->token;
            return response()->json(['token' => $token, 'user' => auth()->user()->id]);
        }
        return response()->json(['error' => 'Invalid credentials']);
    }

    public function register()
    {
        $email = request('email');
        $password = request('password');
        $name = request('name');
        $user = User::create([
            'email' => $email,
            'name' => $name,
            'password' => $password,
        ]);
        $token = $user->createToken('api_token')->token;
        return response()->json(['token' => $token, 'user' => $user->id]);
    }
}
```